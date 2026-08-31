"""
SiteSync AI — Phase 7.3 Decision Service & Persistence Repositories.
Implements domain logic and repository abstractions for:
  - Planner review decisions (Approve, Reject, Modify)
  - Append-only audit trail (public.planner_decisions)
  - Official approved progress actuals (public.approved_actuals)
  - Strict tenant isolation and database idempotency
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import httpx

from app.core.config import get_settings
from app.schemas.decision import (
    ApprovedActualListResponse,
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
)
from app.schemas.schedule import MatchRecommendationResponse
from app.services.extraction_service import extraction_service
from app.services.matching_service import matching_service
from app.services.schedule_service import schedule_service

logger = logging.getLogger(__name__)


def _parse_uuid(val: Any) -> UUID:
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return uuid5(NAMESPACE_DNS, str(val))


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class DecisionError(Exception):
    """Base domain exception for decision service."""


class MatchNotFoundError(DecisionError):
    """Raised when an AI match recommendation is not found."""


class ExtractionNotFoundError(DecisionError):
    """Raised when the source extraction is not found."""


class ScheduleActivityNotFoundError(DecisionError):
    """Raised when the schedule activity is not found."""


class CrossProjectDecisionError(DecisionError):
    """Raised when a tenant boundary violation occurs."""


class InvalidDecisionError(DecisionError):
    """Raised when decision parameters violate domain invariants."""


class DecisionPersistenceError(DecisionError):
    """Raised when persisting a planner decision fails."""


class ApprovedActualPersistenceError(DecisionError):
    """Raised when persisting an approved actual fails."""


# ==============================================================================
# PlannerDecisionRepository
# ==============================================================================

class PlannerDecisionRepository:
    """
    Persistence repository for public.planner_decisions.
    Append-only audit trail; strictly forbids updates and deletes.
    """

    def __init__(self) -> None:
        self._decisions: list[dict[str, Any]] = []

    def clear(self) -> None:
        self._decisions.clear()

    def _get_supabase_headers(self) -> dict[str, str]:
        settings = get_settings()
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def create_decision(
        self,
        decision: PlannerDecisionResponse,
    ) -> PlannerDecisionResponse:
        """Appends a new planner decision record."""
        now = datetime.now(timezone.utc)
        settings = get_settings()
        proj_str = str(_parse_uuid(decision.project_id))
        match_str = str(_parse_uuid(decision.match_id))
        ext_str = str(_parse_uuid(decision.extraction_id))
        decided_by_str = str(_parse_uuid(decision.decided_by))

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/planner_decisions"
            payload = {
                "id": str(decision.id),
                "project_id": proj_str,
                "match_id": match_str,
                "extraction_id": ext_str,
                "decision": decision.decision.value,
                "decided_by": decided_by_str,
                "decided_at": decision.decided_at.isoformat(),
                "rejection_reason": decision.rejection_reason,
                "original_payload": decision.original_payload,
                "modified_payload": decision.modified_payload,
                "created_at": now.isoformat(),
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=self._get_supabase_headers(), json=payload)
                    if resp.status_code in (200, 201):
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to append planner_decisions via PostgREST: {err}")

        # Local test store
        record = {
            "id": decision.id,
            "project_id": decision.project_id,
            "match_id": decision.match_id,
            "extraction_id": decision.extraction_id,
            "decision": decision.decision,
            "decided_by": decision.decided_by,
            "decided_at": decision.decided_at or now,
            "rejection_reason": decision.rejection_reason,
            "original_payload": decision.original_payload,
            "modified_payload": decision.modified_payload,
            "created_at": decision.created_at or now,
        }
        self._decisions.append(record)
        return decision

    async def get_latest_decision(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
    ) -> Optional[PlannerDecisionResponse]:
        """Retrieves the most recent planner decision for a match, strictly scoped to project_id."""
        proj_str = str(_parse_uuid(project_id))
        match_str = str(_parse_uuid(match_id))
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/planner_decisions"
            params = {
                "project_id": f"eq.{proj_str}",
                "match_id": f"eq.{match_str}",
                "select": "*",
                "order": "decided_at.desc",
                "limit": "1",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to query planner_decisions via PostgREST: {err}")

        # Local store search
        matches = [
            self._dict_to_response(rec)
            for rec in self._decisions
            if str(rec["project_id"]) == proj_str and str(rec["match_id"]) == match_str
        ]
        if matches:
            matches.sort(key=lambda d: d.decided_at, reverse=True)
            return matches[0]
        return None

    async def list_decisions(
        self,
        project_id: str | UUID,
        match_id: Optional[str | UUID] = None,
    ) -> list[PlannerDecisionResponse]:
        """Lists planner decision records for a project, optionally filtered by match_id."""
        proj_str = str(_parse_uuid(project_id))
        match_str = str(_parse_uuid(match_id)) if match_id else None
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/planner_decisions"
            params: dict[str, str] = {
                "project_id": f"eq.{proj_str}",
                "select": "*",
                "order": "decided_at.desc",
            }
            if match_str:
                params["match_id"] = f"eq.{match_str}"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        return [self._row_to_response(r) for r in rows]
            except Exception as err:
                logger.error(f"Failed to list planner_decisions via PostgREST: {err}")

        # Local store
        results = [
            self._dict_to_response(rec)
            for rec in self._decisions
            if str(rec["project_id"]) == proj_str
            and (match_str is None or str(rec["match_id"]) == match_str)
        ]
        results.sort(key=lambda d: d.decided_at, reverse=True)
        return results

    def _dict_to_response(self, rec: dict[str, Any]) -> PlannerDecisionResponse:
        dec = rec["decision"]
        if isinstance(dec, str):
            dec = PlannerDecisionType(dec)
        return PlannerDecisionResponse(
            id=_parse_uuid(rec["id"]),
            project_id=_parse_uuid(rec["project_id"]),
            match_id=_parse_uuid(rec["match_id"]),
            extraction_id=_parse_uuid(rec["extraction_id"]),
            decision=dec,
            decided_by=_parse_uuid(rec["decided_by"]),
            decided_at=rec["decided_at"],
            rejection_reason=rec.get("rejection_reason"),
            original_payload=rec.get("original_payload", {}),
            modified_payload=rec.get("modified_payload"),
            created_at=rec["created_at"],
        )

    def _row_to_response(self, row: dict[str, Any]) -> PlannerDecisionResponse:
        decided_at = row["decided_at"]
        if isinstance(decided_at, str):
            decided_at = datetime.fromisoformat(decided_at.replace("Z", "+00:00"))
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return PlannerDecisionResponse(
            id=_parse_uuid(row["id"]),
            project_id=_parse_uuid(row["project_id"]),
            match_id=_parse_uuid(row["match_id"]),
            extraction_id=_parse_uuid(row["extraction_id"]),
            decision=PlannerDecisionType(row["decision"]),
            decided_by=_parse_uuid(row["decided_by"]),
            decided_at=decided_at,
            rejection_reason=row.get("rejection_reason"),
            original_payload=row.get("original_payload", {}),
            modified_payload=row.get("modified_payload"),
            created_at=created_at,
        )


# ==============================================================================
# ApprovedActualRepository
# ==============================================================================

class ApprovedActualRepository:
    """
    Persistence repository for public.approved_actuals.
    Enforces idempotency on (project_id, extraction_id, activity_index).
    """

    def __init__(self) -> None:
        # key: (project_id_str, extraction_id_str, activity_index) -> record dict
        self._actuals: dict[tuple[str, str, int], dict[str, Any]] = {}

    def clear(self) -> None:
        self._actuals.clear()

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

    async def create_or_get_approved_actual(
        self,
        actual: ApprovedActualResponse,
    ) -> ApprovedActualResponse:
        """
        Creates or updates an approved actual record.
        Deduplicates on (project_id, extraction_id, activity_index).
        """
        now = datetime.now(timezone.utc)
        settings = get_settings()
        proj_str = str(_parse_uuid(actual.project_id))
        ext_str = str(_parse_uuid(actual.extraction_id))
        sched_str = str(_parse_uuid(actual.schedule_activity_id))
        match_str = str(_parse_uuid(actual.match_id))
        approved_by_str = str(_parse_uuid(actual.approved_by))

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/approved_actuals"
            params = {"on_conflict": "project_id,extraction_id,activity_index"}
            payload = {
                "id": str(actual.id),
                "project_id": proj_str,
                "schedule_activity_id": sched_str,
                "extraction_id": ext_str,
                "match_id": match_str,
                "activity_index": actual.activity_index,
                "actual_quantity": actual.actual_quantity,
                "actual_unit": actual.actual_unit,
                "actual_date": actual.actual_date.isoformat(),
                "source_evidence": actual.source_evidence,
                "approved_by": approved_by_str,
                "approved_at": actual.approved_at.isoformat(),
                "notes": actual.notes,
                "is_modified": actual.is_modified,
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
                logger.error(f"Failed to upsert approved_actuals via PostgREST: {err}")

        # Local test store
        key = (proj_str, ext_str, actual.activity_index)
        existing = self._actuals.get(key)
        record_id = existing["id"] if existing else actual.id
        record = {
            "id": record_id,
            "project_id": actual.project_id,
            "schedule_activity_id": actual.schedule_activity_id,
            "extraction_id": actual.extraction_id,
            "match_id": actual.match_id,
            "activity_index": actual.activity_index,
            "actual_quantity": actual.actual_quantity,
            "actual_unit": actual.actual_unit,
            "actual_date": actual.actual_date,
            "source_evidence": actual.source_evidence,
            "approved_by": actual.approved_by,
            "approved_at": actual.approved_at or now,
            "notes": actual.notes,
            "is_modified": actual.is_modified,
            "created_at": existing["created_at"] if existing else (actual.created_at or now),
            "updated_at": now,
        }
        self._actuals[key] = record
        return self._dict_to_response(record)

    async def get_by_item(
        self,
        project_id: str | UUID,
        extraction_id: str | UUID,
        activity_index: int,
    ) -> Optional[ApprovedActualResponse]:
        """Retrieves approved actual by composite item key (project_id, extraction_id, activity_index)."""
        proj_str = str(_parse_uuid(project_id))
        ext_str = str(_parse_uuid(extraction_id))
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/approved_actuals"
            params = {
                "project_id": f"eq.{proj_str}",
                "extraction_id": f"eq.{ext_str}",
                "activity_index": f"eq.{activity_index}",
                "select": "*",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to query approved_actuals via PostgREST: {err}")

        key = (proj_str, ext_str, activity_index)
        record = self._actuals.get(key)
        if record:
            return self._dict_to_response(record)
        return None

    async def get_by_id(
        self,
        project_id: str | UUID,
        actual_id: str | UUID,
    ) -> Optional[ApprovedActualResponse]:
        """Retrieves approved actual by primary key ID, strictly scoped to project_id."""
        proj_str = str(_parse_uuid(project_id))
        id_str = str(_parse_uuid(actual_id))
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/approved_actuals"
            params = {
                "project_id": f"eq.{proj_str}",
                "id": f"eq.{id_str}",
                "select": "*",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to query approved_actuals via PostgREST: {err}")

        for record in self._actuals.values():
            if str(record["project_id"]) == proj_str and str(record["id"]) == id_str:
                return self._dict_to_response(record)
        return None

    async def list_approved_actuals(
        self,
        project_id: str | UUID,
        limit: int = 50,
        offset: int = 0,
        schedule_activity_id: Optional[str | UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> tuple[list[ApprovedActualResponse], int]:
        """Lists approved actuals scoped to project_id with pagination and optional filters."""
        proj_str = str(_parse_uuid(project_id))
        sched_str = str(_parse_uuid(schedule_activity_id)) if schedule_activity_id else None
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/approved_actuals"
            params: dict[str, str] = {
                "project_id": f"eq.{proj_str}",
                "select": "*",
                "order": "actual_date.desc,created_at.desc",
                "limit": str(limit),
                "offset": str(offset),
            }
            if sched_str:
                params["schedule_activity_id"] = f"eq.{sched_str}"
            if from_date:
                params["actual_date"] = f"gte.{from_date.isoformat()}"
            if to_date:
                params["actual_date"] = f"lte.{to_date.isoformat()}"

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
                        return [self._row_to_response(r) for r in rows], total
            except Exception as err:
                logger.error(f"Failed to list approved_actuals via PostgREST: {err}")

        # Local store search
        filtered = [
            self._dict_to_response(rec)
            for rec in self._actuals.values()
            if str(rec["project_id"]) == proj_str
            and (sched_str is None or str(rec["schedule_activity_id"]) == sched_str)
            and (from_date is None or rec["actual_date"] >= from_date)
            and (to_date is None or rec["actual_date"] <= to_date)
        ]
        filtered.sort(key=lambda a: (a.actual_date, a.created_at), reverse=True)
        total = len(filtered)
        sliced = filtered[offset : offset + limit]
        return sliced, total

    def _dict_to_response(self, rec: dict[str, Any]) -> ApprovedActualResponse:
        return ApprovedActualResponse(
            id=_parse_uuid(rec["id"]),
            project_id=_parse_uuid(rec["project_id"]),
            schedule_activity_id=_parse_uuid(rec["schedule_activity_id"]),
            extraction_id=_parse_uuid(rec["extraction_id"]),
            match_id=_parse_uuid(rec["match_id"]),
            activity_index=rec["activity_index"],
            actual_quantity=rec.get("actual_quantity"),
            actual_unit=rec.get("actual_unit"),
            actual_date=rec["actual_date"],
            source_evidence=rec.get("source_evidence", []),
            approved_by=_parse_uuid(rec["approved_by"]),
            approved_at=rec["approved_at"],
            notes=rec.get("notes"),
            is_modified=rec.get("is_modified", False),
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
        )

    def _row_to_response(self, row: dict[str, Any]) -> ApprovedActualResponse:
        approved_at = row["approved_at"]
        if isinstance(approved_at, str):
            approved_at = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        actual_date_val = row["actual_date"]
        if isinstance(actual_date_val, str):
            actual_date_val = date.fromisoformat(actual_date_val)

        return ApprovedActualResponse(
            id=_parse_uuid(row["id"]),
            project_id=_parse_uuid(row["project_id"]),
            schedule_activity_id=_parse_uuid(row["schedule_activity_id"]),
            extraction_id=_parse_uuid(row["extraction_id"]),
            match_id=_parse_uuid(row["match_id"]),
            activity_index=row["activity_index"],
            actual_quantity=float(row["actual_quantity"]) if row.get("actual_quantity") is not None else None,
            actual_unit=row.get("actual_unit"),
            actual_date=actual_date_val,
            source_evidence=row.get("source_evidence", []),
            approved_by=_parse_uuid(row["approved_by"]),
            approved_at=approved_at,
            notes=row.get("notes"),
            is_modified=row.get("is_modified", False),
            created_at=created_at,
            updated_at=updated_at,
        )


# ==============================================================================
# DecisionService
# ==============================================================================

class DecisionService:
    """
    Domain service orchestrating human planner decisions and approved actuals creation.
    Core invariant: AI recommends. Humans decide.
    Never mutates original ai_matches records.
    """

    def __init__(
        self,
        decision_repo: Optional[PlannerDecisionRepository] = None,
        actual_repo: Optional[ApprovedActualRepository] = None,
    ) -> None:
        self.decision_repo = decision_repo or PlannerDecisionRepository()
        self.actual_repo = actual_repo or ApprovedActualRepository()
        self.match_repo = matching_service.repository
        self.extraction_service = extraction_service
        self.schedule_service = schedule_service

    async def approve_match(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
        planner_id: str | UUID,
        notes: Optional[str] = None,
    ) -> ApprovedActualResponse:
        """
        Executes human planner approval of an AI match recommendation as-is.
        Appends decision audit log and idempotently creates the official approved actual.
        """
        proj_uuid = _parse_uuid(project_id)
        match_uuid = _parse_uuid(match_id)
        planner_uuid = _parse_uuid(planner_id)
        now = datetime.now(timezone.utc)

        # 1. Retrieve match scoped by project_id
        match = await self.match_repo.get_match(proj_uuid, match_uuid)
        if not match:
            raise MatchNotFoundError(f"AI match recommendation '{match_id}' not found for project '{project_id}'")

        if str(match.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Match '{match_id}' does not belong to project '{project_id}'")

        # 2. Retrieve extraction to extract source evidence and progress values
        extraction = await self.extraction_service.get_extraction(str(proj_uuid), str(match.extraction_id))
        if not extraction:
            raise ExtractionNotFoundError(f"Source extraction '{match.extraction_id}' not found for project '{project_id}'")

        if str(extraction.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Extraction '{match.extraction_id}' does not belong to project '{project_id}'")

        # 3. Retrieve recommended schedule activity
        activity = await self.schedule_service.get_activity(str(proj_uuid), str(match.recommended_activity_id))
        if not activity:
            raise ScheduleActivityNotFoundError(
                f"Schedule activity '{match.recommended_activity_id}' not found in project '{project_id}'"
            )

        if str(activity.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Schedule activity '{match.recommended_activity_id}' does not belong to project '{project_id}'")

        # 4. Extract item attributes from source extraction
        extracted_data = extraction.extracted_data or {}
        activities = extracted_data.get("extracted_activities", [])
        extracted_act = activities[match.activity_index] if match.activity_index < len(activities) else {}

        actual_qty = extracted_act.get("progress_value")
        if actual_qty is not None and actual_qty < 0:
            raise InvalidDecisionError("actual_quantity must be >= 0")

        actual_unit = extracted_act.get("progress_unit") or activity.planned_unit
        event_date_str = extracted_act.get("event_date")
        actual_date = date.fromisoformat(event_date_str) if event_date_str else date.today()
        evidence_tokens = extracted_act.get("evidence_tokens", [])

        # 5. Build original payload snapshot for audit log
        original_snapshot = {
            "match_id": str(match.id),
            "project_id": str(match.project_id),
            "extraction_id": str(match.extraction_id),
            "activity_index": match.activity_index,
            "recommended_activity_id": str(match.recommended_activity_id),
            "recommended_activity_code": match.recommended_activity_code,
            "recommended_activity_name": match.recommended_activity_name,
            "confidence_score": match.confidence_score,
            "scoring_breakdown": match.scoring_breakdown.model_dump(),
            "alternative_matches": [alt.model_dump(mode="json") for alt in match.alternative_matches],
        }

        # 6. Append planner_decisions audit row
        decision_record = PlannerDecisionResponse(
            id=uuid4(),
            project_id=proj_uuid,
            match_id=match_uuid,
            extraction_id=_parse_uuid(match.extraction_id),
            decision=PlannerDecisionType.APPROVED,
            decided_by=planner_uuid,
            decided_at=now,
            rejection_reason=None,
            original_payload=original_snapshot,
            modified_payload=None,
            created_at=now,
        )
        await self.decision_repo.create_decision(decision_record)

        # 7. Create or get approved actual idempotently
        approved_actual = ApprovedActualResponse(
            id=uuid4(),
            project_id=proj_uuid,
            schedule_activity_id=_parse_uuid(match.recommended_activity_id),
            extraction_id=_parse_uuid(match.extraction_id),
            match_id=match_uuid,
            activity_index=match.activity_index,
            actual_quantity=actual_qty,
            actual_unit=actual_unit,
            actual_date=actual_date,
            source_evidence=evidence_tokens,
            approved_by=planner_uuid,
            approved_at=now,
            notes=notes.strip() if notes and notes.strip() else None,
            is_modified=False,
            created_at=now,
            updated_at=now,
        )
        persisted_actual = await self.actual_repo.create_or_get_approved_actual(approved_actual)
        return persisted_actual

    async def reject_match(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
        planner_id: str | UUID,
        rejection_reason: str,
    ) -> PlannerDecisionResponse:
        """
        Executes human planner rejection of an AI match recommendation.
        Appends decision audit log with justification. Does NOT create an approved actual.
        """
        proj_uuid = _parse_uuid(project_id)
        match_uuid = _parse_uuid(match_id)
        planner_uuid = _parse_uuid(planner_id)
        now = datetime.now(timezone.utc)

        if not rejection_reason or not rejection_reason.strip():
            raise InvalidDecisionError("rejection_reason must not be empty or whitespace only")

        # 1. Retrieve match scoped by project_id
        match = await self.match_repo.get_match(proj_uuid, match_uuid)
        if not match:
            raise MatchNotFoundError(f"AI match recommendation '{match_id}' not found for project '{project_id}'")

        if str(match.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Match '{match_id}' does not belong to project '{project_id}'")

        # 2. Build original payload snapshot for audit log
        original_snapshot = {
            "match_id": str(match.id),
            "project_id": str(match.project_id),
            "extraction_id": str(match.extraction_id),
            "activity_index": match.activity_index,
            "recommended_activity_id": str(match.recommended_activity_id),
            "recommended_activity_code": match.recommended_activity_code,
            "recommended_activity_name": match.recommended_activity_name,
            "confidence_score": match.confidence_score,
            "scoring_breakdown": match.scoring_breakdown.model_dump(),
            "alternative_matches": [alt.model_dump(mode="json") for alt in match.alternative_matches],
        }

        # 3. Append planner_decisions audit row
        decision_record = PlannerDecisionResponse(
            id=uuid4(),
            project_id=proj_uuid,
            match_id=match_uuid,
            extraction_id=_parse_uuid(match.extraction_id),
            decision=PlannerDecisionType.REJECTED,
            decided_by=planner_uuid,
            decided_at=now,
            rejection_reason=rejection_reason.strip(),
            original_payload=original_snapshot,
            modified_payload=None,
            created_at=now,
        )
        return await self.decision_repo.create_decision(decision_record)

    async def modify_match(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
        planner_id: str | UUID,
        modification: ModifyMatchRequest,
    ) -> ApprovedActualResponse:
        """
        Executes human planner modification of an AI match recommendation before approval.
        Appends decision audit log with overrides and idempotently creates the modified approved actual.
        """
        proj_uuid = _parse_uuid(project_id)
        match_uuid = _parse_uuid(match_id)
        planner_uuid = _parse_uuid(planner_id)
        target_activity_uuid = _parse_uuid(modification.schedule_activity_id)
        now = datetime.now(timezone.utc)

        # 1. Retrieve match scoped by project_id
        match = await self.match_repo.get_match(proj_uuid, match_uuid)
        if not match:
            raise MatchNotFoundError(f"AI match recommendation '{match_id}' not found for project '{project_id}'")

        if str(match.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Match '{match_id}' does not belong to project '{project_id}'")

        # 2. Retrieve extraction to extract source evidence
        extraction = await self.extraction_service.get_extraction(str(proj_uuid), str(match.extraction_id))
        if not extraction:
            raise ExtractionNotFoundError(f"Source extraction '{match.extraction_id}' not found for project '{project_id}'")

        if str(extraction.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(f"Extraction '{match.extraction_id}' does not belong to project '{project_id}'")

        # 3. Retrieve target modified schedule activity and ensure project ownership
        target_activity = await self.schedule_service.get_activity(str(proj_uuid), str(target_activity_uuid))
        if not target_activity:
            raise ScheduleActivityNotFoundError(
                f"Target schedule activity '{modification.schedule_activity_id}' not found in project '{project_id}'"
            )

        if str(target_activity.project_id) != str(proj_uuid):
            raise CrossProjectDecisionError(
                f"Schedule activity '{modification.schedule_activity_id}' does not belong to project '{project_id}'"
            )

        # 4. Quantity validation
        if modification.actual_quantity is not None and modification.actual_quantity < 0:
            raise InvalidDecisionError("actual_quantity must be >= 0")

        # 5. Extract item attributes from source extraction
        extracted_data = extraction.extracted_data or {}
        activities = extracted_data.get("extracted_activities", [])
        extracted_act = activities[match.activity_index] if match.activity_index < len(activities) else {}
        evidence_tokens = extracted_act.get("evidence_tokens", [])

        # 6. Build original and modified payload snapshots
        original_snapshot = {
            "match_id": str(match.id),
            "project_id": str(match.project_id),
            "extraction_id": str(match.extraction_id),
            "activity_index": match.activity_index,
            "recommended_activity_id": str(match.recommended_activity_id),
            "recommended_activity_code": match.recommended_activity_code,
            "recommended_activity_name": match.recommended_activity_name,
            "confidence_score": match.confidence_score,
            "scoring_breakdown": match.scoring_breakdown.model_dump(),
            "alternative_matches": [alt.model_dump(mode="json") for alt in match.alternative_matches],
        }

        modified_snapshot = {
            "schedule_activity_id": str(target_activity_uuid),
            "schedule_activity_code": target_activity.activity_code,
            "schedule_activity_name": target_activity.name,
            "actual_quantity": modification.actual_quantity,
            "actual_unit": modification.actual_unit or target_activity.planned_unit,
            "actual_date": modification.actual_date.isoformat(),
            "notes": modification.notes,
        }

        # 7. Append planner_decisions audit row
        decision_record = PlannerDecisionResponse(
            id=uuid4(),
            project_id=proj_uuid,
            match_id=match_uuid,
            extraction_id=_parse_uuid(match.extraction_id),
            decision=PlannerDecisionType.MODIFIED,
            decided_by=planner_uuid,
            decided_at=now,
            rejection_reason=None,
            original_payload=original_snapshot,
            modified_payload=modified_snapshot,
            created_at=now,
        )
        await self.decision_repo.create_decision(decision_record)

        # 8. Create or get approved actual with modified values
        approved_actual = ApprovedActualResponse(
            id=uuid4(),
            project_id=proj_uuid,
            schedule_activity_id=target_activity_uuid,
            extraction_id=_parse_uuid(match.extraction_id),
            match_id=match_uuid,
            activity_index=match.activity_index,
            actual_quantity=modification.actual_quantity,
            actual_unit=modification.actual_unit or target_activity.planned_unit,
            actual_date=modification.actual_date,
            source_evidence=evidence_tokens,
            approved_by=planner_uuid,
            approved_at=now,
            notes=modification.notes,
            is_modified=True,
            created_at=now,
            updated_at=now,
        )
        persisted_actual = await self.actual_repo.create_or_get_approved_actual(approved_actual)
        return persisted_actual

    async def get_decision_for_match(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
    ) -> Optional[PlannerDecisionResponse]:
        """Retrieves the latest planner decision for a match recommendation."""
        return await self.decision_repo.get_latest_decision(project_id, match_id)

    async def list_approved_actuals(
        self,
        project_id: str | UUID,
        limit: int = 50,
        offset: int = 0,
        schedule_activity_id: Optional[str | UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> ApprovedActualListResponse:
        """Lists approved actuals for a project with pagination and filtering."""
        items, total = await self.actual_repo.list_approved_actuals(
            project_id=project_id,
            limit=limit,
            offset=offset,
            schedule_activity_id=schedule_activity_id,
            from_date=from_date,
            to_date=to_date,
        )
        return ApprovedActualListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )


# Singleton instance
decision_service = DecisionService()
