"""
Schedule Activity Domain Service — SiteSync AI Phase 6.3.
Manages schedule activity ingestion, listing, and persistence with database-level
idempotency on (project_id, activity_code) and strict project scoping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.schemas.schedule import (
    ScheduleActivityCreate,
    ScheduleActivityListResponse,
    ScheduleActivityResponse,
)

logger = logging.getLogger(__name__)


class ScheduleError(Exception):
    """Base domain schedule exception."""


class ScheduleActivityNotFoundError(ScheduleError):
    """Raised when a schedule activity does not exist or does not belong to the project."""


class ScheduleService:
    """
    Domain service for project schedule activities.
    Supports Supabase PostgREST persistence with atomic upsert (on_conflict=project_id,activity_code)
    and an in-memory test store with unique indexing for offline execution.
    """

    def __init__(self) -> None:
        # key: activity_id (str) -> dict
        self._activities: dict[str, dict[str, Any]] = {}
        # key: (project_id, activity_code) -> activity_id (str)
        self._unique_index: dict[tuple[str, str], str] = {}

    def clear(self) -> None:
        """Resets in-memory records (used in test isolation)."""
        self._activities.clear()
        self._unique_index.clear()

    def _get_supabase_headers(self, merge_duplicates: bool = False) -> dict[str, str]:
        settings = get_settings()
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        prefer = "resolution=merge-duplicates,return=representation" if merge_duplicates else "return=representation"
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    async def create_or_update_activity(
        self,
        project_id: str,
        data: ScheduleActivityCreate,
    ) -> ScheduleActivityResponse:
        """
        Creates or idempotently updates a schedule activity scoped to project_id.
        Deduplicates on (project_id, activity_code).
        """
        now = datetime.now(timezone.utc)
        settings = get_settings()

        # Try Supabase PostgREST in live environment
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_activities"
            params = {"on_conflict": "project_id,activity_code"}
            payload = {
                "project_id": project_id,
                "activity_code": data.activity_code,
                "name": data.name,
                "wbs_code": data.wbs_code,
                "discipline": data.discipline,
                "location": data.location,
                "planned_start_date": data.planned_start_date.isoformat() if data.planned_start_date else None,
                "planned_finish_date": data.planned_finish_date.isoformat() if data.planned_finish_date else None,
                "planned_quantity": data.planned_quantity,
                "planned_unit": data.planned_unit,
                "metadata": data.metadata,
                "updated_at": now.isoformat(),
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        url,
                        headers=self._get_supabase_headers(merge_duplicates=True),
                        params=params,
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to upsert schedule activity via PostgREST: {err}")

        # Local / test store execution with idempotent unique indexing
        unique_key = (project_id, data.activity_code)
        existing_id = self._unique_index.get(unique_key)

        if existing_id and existing_id in self._activities:
            record = self._activities[existing_id]
            record.update({
                "name": data.name,
                "wbs_code": data.wbs_code,
                "discipline": data.discipline,
                "location": data.location,
                "planned_start_date": data.planned_start_date,
                "planned_finish_date": data.planned_finish_date,
                "planned_quantity": data.planned_quantity,
                "planned_unit": data.planned_unit,
                "metadata": data.metadata,
                "updated_at": now,
            })
        else:
            new_id = str(uuid4())
            record = {
                "id": new_id,
                "project_id": project_id,
                "activity_code": data.activity_code,
                "name": data.name,
                "wbs_code": data.wbs_code,
                "discipline": data.discipline,
                "location": data.location,
                "planned_start_date": data.planned_start_date,
                "planned_finish_date": data.planned_finish_date,
                "planned_quantity": data.planned_quantity,
                "planned_unit": data.planned_unit,
                "metadata": data.metadata,
                "created_at": now,
                "updated_at": now,
            }
            self._activities[new_id] = record
            self._unique_index[unique_key] = new_id

        return self._to_response(record)

    async def list_activities(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> ScheduleActivityListResponse:
        """
        Lists schedule activities scoped to a specific project with pagination.
        """
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_activities"
            params = {
                "project_id": f"eq.{project_id}",
                "select": "*",
                "order": "activity_code.asc",
                "limit": str(limit),
                "offset": str(offset),
            }
            headers = self._get_supabase_headers()
            headers["Prefer"] = "count=exact"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        total = len(rows)
                        content_range = resp.headers.get("content-range")
                        if content_range and "/" in content_range:
                            try:
                                total = int(content_range.split("/")[1])
                            except ValueError:
                                pass
                        items = [self._row_to_response(r) for r in rows]
                        return ScheduleActivityListResponse(
                            items=items,
                            total=total,
                            limit=limit,
                            offset=offset,
                        )
            except Exception as err:
                logger.error(f"Failed to query schedule activities via PostgREST: {err}")

        # Local / test store execution
        matching = [
            act for act in self._activities.values()
            if act.get("project_id") == project_id
        ]
        matching.sort(key=lambda x: x.get("activity_code", ""))
        total = len(matching)
        sliced = matching[offset : offset + limit]
        items = [self._to_response(act) for act in sliced]

        return ScheduleActivityListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_activity(
        self,
        project_id: str,
        activity_id: str,
    ) -> ScheduleActivityResponse | None:
        """
        Retrieves a single schedule activity scoped to a project.
        """
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/schedule_activities"
            params = {
                "id": f"eq.{activity_id}",
                "project_id": f"eq.{project_id}",
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
                logger.error(f"Failed to get schedule activity via PostgREST: {err}")

        record = self._activities.get(activity_id)
        if record and record.get("project_id") == project_id:
            return self._to_response(record)
        return None

    def _parse_uuid(self, val: Any) -> UUID:
        if isinstance(val, UUID):
            return val
        try:
            return UUID(str(val))
        except (ValueError, AttributeError):
            import uuid
            return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))

    def _to_response(self, record: dict[str, Any]) -> ScheduleActivityResponse:
        return ScheduleActivityResponse(
            id=self._parse_uuid(record["id"]),
            project_id=self._parse_uuid(record["project_id"]),
            activity_code=record["activity_code"],
            name=record["name"],
            wbs_code=record.get("wbs_code"),
            discipline=record.get("discipline"),
            location=record.get("location"),
            planned_start_date=record.get("planned_start_date"),
            planned_finish_date=record.get("planned_finish_date"),
            planned_quantity=record.get("planned_quantity"),
            planned_unit=record.get("planned_unit"),
            metadata=record.get("metadata", {}),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def _row_to_response(self, row: dict[str, Any]) -> ScheduleActivityResponse:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return ScheduleActivityResponse(
            id=self._parse_uuid(row["id"]),
            project_id=self._parse_uuid(row["project_id"]),
            activity_code=row["activity_code"],
            name=row["name"],
            wbs_code=row.get("wbs_code"),
            discipline=row.get("discipline"),
            location=row.get("location"),
            planned_start_date=row.get("planned_start_date"),
            planned_finish_date=row.get("planned_finish_date"),
            planned_quantity=row.get("planned_quantity"),
            planned_unit=row.get("planned_unit"),
            metadata=row.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )


# Singleton domain service instance
schedule_service = ScheduleService()
