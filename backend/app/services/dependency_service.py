"""
SiteSync AI — Phase 9.5 Schedule Dependency Domain Service.
Manages schedule dependency edge persistence, tenant isolation, and graph validation
with database-level unique constraints and service-level cycle detection (ADR-014).
Supports Supabase PostgREST persistence and in-memory test store.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.schemas.cpm import (
    CPMActivityInput,
    CPMDependencyInput,
    DependencyRelationshipType,
)
from app.schemas.network import DependencyCreate, DependencyResponse
from app.services.cpm_service import (
    CPMGraphCycleError,
    CPMService,
    CPMValidationError,
)
from app.services.schedule_service import schedule_service

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """Base exception for dependency domain operations."""
    pass


class DependencyNotFoundError(DependencyError):
    """Raised when a dependency edge does not exist or does not belong to the project."""
    pass


class DependencyActivityNotFoundError(DependencyError):
    """Raised when predecessor or successor activity does not exist in the project."""
    pass


class DependencyDuplicateError(DependencyError):
    """Raised when a dependency edge between the same predecessor and successor already exists."""
    pass


class DependencyValidationError(DependencyError):
    """Raised when dependency input parameters fail validation."""
    pass


class DependencyCycleError(DependencyError):
    """Raised when adding a dependency introduces a directed cycle in the schedule DAG."""
    pass


def _parse_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


class DependencyService:
    """
    Domain service for schedule dependencies.
    Provides tenant-isolated CRUD operations with cycle detection and deterministic sorting.
    Uses per-project serialization locking to guarantee concurrency-safe graph validation.
    """

    def __init__(self) -> None:
        # key: dependency_id (str) -> dict
        self._dependencies: dict[str, dict[str, Any]] = {}
        # key: (project_id, predecessor_id, successor_id) -> dependency_id (str)
        self._unique_index: dict[tuple[str, str, str], str] = {}
        # key: project_id (str) -> asyncio.Lock
        self._project_locks: dict[str, asyncio.Lock] = {}
        self.schedule_service = schedule_service
        self.cpm_engine = CPMService()

    def clear(self) -> None:
        """Resets in-memory records (used in test isolation)."""
        self._dependencies.clear()
        self._unique_index.clear()
        self._project_locks.clear()


    def _get_supabase_headers(self) -> dict[str, str]:
        settings = get_settings()
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def list_dependencies(self, project_id: str | UUID) -> list[DependencyResponse]:
        """
        Retrieves all dependency edges belonging strictly to project_id,
        sorted deterministically by (predecessor_id ASC, successor_id ASC, id ASC).
        """
        proj_str = str(project_id)
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_dependencies"
            params = {
                "project_id": f"eq.{proj_str}",
                "select": "*",
                "order": "predecessor_id.asc,successor_id.asc,id.asc",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        return [self._row_to_response(r) for r in rows]
            except Exception as err:
                logger.error(f"Failed to query schedule dependencies via PostgREST: {err}")

        # In-memory test store
        matching = [
            dep for dep in self._dependencies.values()
            if dep.get("project_id") == proj_str
        ]
        # Deterministic ordering: predecessor_id, successor_id, id
        matching.sort(key=lambda d: (str(d["predecessor_id"]), str(d["successor_id"]), str(d["id"])))
        return [self._to_response(d) for d in matching]

    async def get_dependency(
        self,
        project_id: str | UUID,
        dependency_id: str | UUID,
    ) -> DependencyResponse | None:
        """
        Retrieves a single dependency edge scoped strictly to project_id.
        """
        proj_str = str(project_id)
        dep_str = str(dependency_id)
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_dependencies"
            params = {
                "id": f"eq.{dep_str}",
                "project_id": f"eq.{proj_str}",
                "select": "*",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
                        return None
            except Exception as err:
                logger.error(f"Failed to get schedule dependency via PostgREST: {err}")

        record = self._dependencies.get(dep_str)
        if record and record.get("project_id") == proj_str:
            return self._to_response(record)
        return None

    async def create_dependency(
        self,
        project_id: str | UUID,
        data: DependencyCreate,
    ) -> DependencyResponse:
        """
        Validates and creates a new schedule dependency edge.
        Performs tenant isolation, existence validation, self-loop checking,
        duplicate edge checking, and DAG cycle validation via topological sort.
        Serializes validation and persistence per-project to eliminate concurrent cycle races.
        """
        proj_uuid = _parse_uuid(project_id)
        proj_str = str(proj_uuid)
        pred_uuid = data.predecessor_id
        succ_uuid = data.successor_id

        # 1. Prevent self dependency
        if pred_uuid == succ_uuid:
            raise DependencyValidationError("Self-dependency is forbidden: predecessor and successor are identical.")

        if proj_str not in self._project_locks:
            self._project_locks[proj_str] = asyncio.Lock()

        async with self._project_locks[proj_str]:
            # 2. Validate predecessor and successor exist in the same project
            activities_resp = await self.schedule_service.list_activities(
                project_id=proj_str,
                limit=10000,
                offset=0,
            )
            activity_map = {act.id: act for act in activities_resp.items}

            if pred_uuid not in activity_map:
                raise DependencyActivityNotFoundError(
                    f"Predecessor activity '{pred_uuid}' not found in project '{proj_str}'"
                )
            if succ_uuid not in activity_map:
                raise DependencyActivityNotFoundError(
                    f"Successor activity '{succ_uuid}' not found in project '{proj_str}'"
                )

            # 3. Check for duplicate edge
            unique_key = (proj_str, str(pred_uuid), str(succ_uuid))
            if unique_key in self._unique_index:
                raise DependencyDuplicateError(
                    f"Dependency edge between predecessor '{pred_uuid}' and successor '{succ_uuid}' already exists in project '{proj_str}'"
                )

            # 4. Check for cycle introduction via CPM/Topological sort
            existing_deps = await self.list_dependencies(proj_str)

            # Construct CPM activity inputs
            cpm_activities = [
                CPMActivityInput(
                    activity_id=act.id,
                    project_id=proj_uuid,
                    activity_code=act.activity_code,
                    name=act.name,
                    wbs_code=act.wbs_code,
                    discipline=act.discipline,
                    location=act.location,
                    planned_start_date=act.planned_start_date,
                    planned_finish_date=act.planned_finish_date,
                )
                for act in activities_resp.items
            ]

            # Construct candidate dependencies with proposed edge
            temp_dep_id = uuid4()
            candidate_cpm_deps = [
                CPMDependencyInput(
                    dependency_id=dep.id,
                    project_id=proj_uuid,
                    predecessor_id=dep.predecessor_id,
                    successor_id=dep.successor_id,
                    relationship_type=dep.relationship_type,
                    lag_days=dep.lag_days,
                )
                for dep in existing_deps
            ]
            candidate_cpm_deps.append(
                CPMDependencyInput(
                    dependency_id=temp_dep_id,
                    project_id=proj_uuid,
                    predecessor_id=pred_uuid,
                    successor_id=succ_uuid,
                    relationship_type=data.relationship_type,
                    lag_days=data.lag_days,
                )
            )

            try:
                # Topological sort validates acyclicity
                self.cpm_engine.topological_sort(cpm_activities, candidate_cpm_deps)
            except CPMGraphCycleError as err:
                logger.warning(f"Cycle detected while attempting to add dependency: {err}")
                raise DependencyCycleError("Dependency cycle detected.") from err
            except CPMValidationError as err:
                logger.warning(f"Validation error while evaluating dependency graph: {err}")
                raise DependencyValidationError(str(err)) from err

            # 5. Persist the new dependency edge
            now = datetime.now(timezone.utc)
            settings = get_settings()

            if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
                url = f"{settings.supabase_url}/rest/v1/schedule_dependencies"
                payload = {
                    "project_id": proj_str,
                    "predecessor_id": str(pred_uuid),
                    "successor_id": str(succ_uuid),
                    "relationship_type": data.relationship_type.value,
                    "lag_days": data.lag_days,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(url, headers=self._get_supabase_headers(), json=payload)
                        if resp.status_code in (200, 201):
                            rows = resp.json()
                            if rows:
                                return self._row_to_response(rows[0])
                except Exception as err:
                    logger.error(f"Failed to insert schedule dependency via PostgREST: {err}")

            # Local / in-memory store persistence
            new_id = str(uuid4())
            record = {
                "id": new_id,
                "project_id": proj_str,
                "predecessor_id": pred_uuid,
                "successor_id": succ_uuid,
                "relationship_type": data.relationship_type,
                "lag_days": data.lag_days,
                "created_at": now,
                "updated_at": now,
            }
            self._dependencies[new_id] = record
            self._unique_index[unique_key] = new_id

            return self._to_response(record)


    async def delete_dependency(
        self,
        project_id: str | UUID,
        dependency_id: str | UUID,
    ) -> bool:
        """
        Deletes a schedule dependency edge scoped strictly to project_id.
        Never permits cross-project deletion.
        """
        proj_str = str(project_id)
        dep_str = str(dependency_id)
        settings = get_settings()

        existing = await self.get_dependency(proj_str, dep_str)
        if not existing or str(existing.project_id) != proj_str:
            raise DependencyNotFoundError(
                f"Dependency '{dep_str}' not found in project '{proj_str}'"
            )

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_dependencies"
            params = {
                "id": f"eq.{dep_str}",
                "project_id": f"eq.{proj_str}",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.delete(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code in (200, 204):
                        return True
            except Exception as err:
                logger.error(f"Failed to delete schedule dependency via PostgREST: {err}")

        # In-memory delete
        if dep_str in self._dependencies:
            record = self._dependencies.pop(dep_str)
            key = (proj_str, str(record["predecessor_id"]), str(record["successor_id"]))
            self._unique_index.pop(key, None)
            return True

        return False

    def _to_response(self, record: dict[str, Any]) -> DependencyResponse:
        rel_type = record["relationship_type"]
        if isinstance(rel_type, str):
            rel_type = DependencyRelationshipType(rel_type)

        return DependencyResponse(
            id=_parse_uuid(record["id"]),
            project_id=_parse_uuid(record["project_id"]),
            predecessor_id=_parse_uuid(record["predecessor_id"]),
            successor_id=_parse_uuid(record["successor_id"]),
            relationship_type=rel_type,
            lag_days=int(record["lag_days"]),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def _row_to_response(self, row: dict[str, Any]) -> DependencyResponse:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        rel_type = row["relationship_type"]
        if isinstance(rel_type, str):
            rel_type = DependencyRelationshipType(rel_type)

        return DependencyResponse(
            id=_parse_uuid(row["id"]),
            project_id=_parse_uuid(row["project_id"]),
            predecessor_id=_parse_uuid(row["predecessor_id"]),
            successor_id=_parse_uuid(row["successor_id"]),
            relationship_type=rel_type,
            lag_days=int(row["lag_days"]),
            created_at=created_at,
            updated_at=updated_at,
        )


dependency_service = DependencyService()
