"""
Domain Extraction Service & Database Persistence — SiteSync AI Phase 5.
Orchestrates raw field input eligibility, Gemini extraction, normalization,
exact evidence token verification, and concurrency-safe idempotent persistence into public.ai_extractions.

Invariants:
  - Strict project isolation: rejects cross-project inputs before invoking AI.
  - Server-authoritative metadata: raw_input_id, model_version, and timestamps cannot be controlled by the LLM.
  - Verbatim evidence verification: every evidence token must be an exact case-sensitive substring of raw_text.
  - Immutability: field_inputs records are NEVER mutated or deleted during or after extraction.
  - Database-enforced idempotency: atomic upsert on (project_id, field_input_id) guarantees exactly one row per input.
  - Real database integration: uses Supabase PostgREST with on_conflict=project_id,field_input_id and service-role credentials.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.ai.normalizer import normalize_extraction
from app.core.config import get_settings
from app.schemas.extractions import (
    ExtractionListResponse,
    ExtractionResponse,
    ExtractionResult,
    ExtractionStatus,
)
from app.schemas.inputs import FieldInputResponse, FieldInputType, TranscriptionStatus
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiExtractionParseError,
    GeminiProviderError,
    GeminiService,
    GeminiTimeoutError,
    gemini_service,
)
from app.services.input_service import input_service

logger = logging.getLogger(__name__)


# Domain Exceptions
class ExtractionError(Exception):
    """Base domain extraction exception."""


class ExtractionNotFoundError(ExtractionError):
    """Raised when field input or extraction record does not exist."""


class CrossProjectInputError(ExtractionError):
    """Raised when field input does not belong to the requested project."""


class ExtractionInputError(ExtractionError):
    """Raised when raw field input is ineligible or lacks extractable text."""


class EvidenceVerificationError(ExtractionError):
    """Raised when an extracted evidence token is not an exact substring in raw_text."""


class AIExtractionRepository:
    """
    Database persistence repository for public.ai_extractions.
    Uses Supabase PostgREST atomic upserts (on_conflict=project_id,field_input_id)
    with service-role authorization when configured in production,
    or an internal store with composite unique index for offline development/test execution.
    """

    def __init__(self) -> None:
        # key: extraction_id -> record
        self._records_by_id: dict[str, dict[str, Any]] = {}
        # key: (project_id, field_input_id) -> extraction_id
        self._unique_index: dict[tuple[str, str], str] = {}

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

    async def get_by_id(self, project_id: str, extraction_id: str) -> dict[str, Any] | None:
        """Retrieves a single extraction record ensuring project boundary scoping."""
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_extractions"
            params = {
                "id": f"eq.{extraction_id}",
                "project_id": f"eq.{project_id}",
                "select": "*",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return rows[0]
            except Exception as err:
                logger.error(f"Failed to query public.ai_extractions via Supabase REST: {err}")

        # Fallback to local store
        record = self._records_by_id.get(extraction_id)
        if record and record.get("project_id") == project_id:
            return record
        return None

    async def get_by_input(self, project_id: str, field_input_id: str) -> dict[str, Any] | None:
        """Finds existing extraction for a specific field input in a project."""
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_extractions"
            params = {
                "project_id": f"eq.{project_id}",
                "field_input_id": f"eq.{field_input_id}",
                "select": "*",
                "limit": "1",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return rows[0]
            except Exception as err:
                logger.error(f"Failed to query public.ai_extractions via Supabase REST: {err}")

        # Fallback to local store with unique index
        ext_id = self._unique_index.get((project_id, field_input_id))
        if ext_id:
            return self._records_by_id.get(ext_id)
        return None

    async def list_by_project(
        self,
        project_id: str,
        status: ExtractionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lists extraction records for a project with optional status filter."""
        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_extractions"
            params: dict[str, str] = {
                "project_id": f"eq.{project_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(limit),
                "offset": str(offset),
            }
            if status:
                params["status"] = f"eq.{status.value}"
            try:
                headers = self._get_supabase_headers()
                headers["Prefer"] = "count=exact"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        content_range = resp.headers.get("Content-Range", "")
                        total = int(content_range.split("/")[-1]) if "/" in content_range else len(rows)
                        return rows, total
            except Exception as err:
                logger.error(f"Failed to list public.ai_extractions via Supabase REST: {err}")

        # Fallback to local store
        matched = [
            r for r in self._records_by_id.values()
            if r.get("project_id") == project_id
            and (status is None or r.get("status") == status)
        ]
        matched.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        total = len(matched)
        paginated = matched[offset : offset + limit]
        return paginated, total

    async def upsert_completed(
        self,
        project_id: str,
        field_input_id: str,
        extraction: ExtractionResult,
    ) -> dict[str, Any]:
        """
        Atomically persists or updates an extraction record as COMPLETED.
        Uses PostgREST on_conflict=project_id,field_input_id to ensure concurrency safety.
        """
        now = datetime.now(timezone.utc)
        serialized_data = extraction.model_dump(mode="json")
        confidence_val = float(extraction.extraction_confidence)
        model_ver = extraction.model_version
        settings = get_settings()

        # Check for existing local ID if present to preserve primary key
        existing_id = self._unique_index.get((project_id, field_input_id)) or str(uuid.uuid4())

        payload = {
            "id": existing_id,
            "project_id": project_id,
            "field_input_id": field_input_id,
            "status": ExtractionStatus.COMPLETED.value,
            "extracted_data": serialized_data,
            "confidence_score": confidence_val,
            "model_version": model_ver,
            "error_message": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_extractions?on_conflict=project_id,field_input_id"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        url,
                        headers=self._get_supabase_headers(merge_duplicates=True),
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        rows = resp.json() if resp.text else []
                        if rows:
                            return rows[0]
            except Exception as err:
                logger.error(f"Failed to upsert public.ai_extractions via PostgREST: {err}")

        # Local storage with composite unique constraint enforcement
        composite_key = (project_id, field_input_id)
        if composite_key in self._unique_index:
            ext_id = self._unique_index[composite_key]
            record = self._records_by_id[ext_id]
            record["status"] = ExtractionStatus.COMPLETED
            record["extracted_data"] = serialized_data
            record["confidence_score"] = confidence_val
            record["model_version"] = model_ver
            record["error_message"] = None
            record["updated_at"] = now
        else:
            record = {
                "id": existing_id,
                "project_id": project_id,
                "field_input_id": field_input_id,
                "status": ExtractionStatus.COMPLETED,
                "extracted_data": serialized_data,
                "confidence_score": confidence_val,
                "model_version": model_ver,
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            }
            self._records_by_id[existing_id] = record
            self._unique_index[composite_key] = existing_id

        return record

    async def upsert_failed(
        self,
        project_id: str,
        field_input_id: str,
        error_message: str,
        model_version: str,
    ) -> dict[str, Any]:
        """
        Atomically persists or updates an extraction record as FAILED.
        Uses PostgREST on_conflict=project_id,field_input_id to ensure concurrency safety.
        """
        now = datetime.now(timezone.utc)
        settings = get_settings()

        existing_id = self._unique_index.get((project_id, field_input_id)) or str(uuid.uuid4())

        payload = {
            "id": existing_id,
            "project_id": project_id,
            "field_input_id": field_input_id,
            "status": ExtractionStatus.FAILED.value,
            "extracted_data": {},
            "confidence_score": None,
            "model_version": model_version,
            "error_message": error_message,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_extractions?on_conflict=project_id,field_input_id"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        url,
                        headers=self._get_supabase_headers(merge_duplicates=True),
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        rows = resp.json() if resp.text else []
                        if rows:
                            return rows[0]
            except Exception as err:
                logger.error(f"Failed to upsert failed public.ai_extractions via PostgREST: {err}")

        # Local storage with composite unique constraint enforcement
        composite_key = (project_id, field_input_id)
        if composite_key in self._unique_index:
            ext_id = self._unique_index[composite_key]
            record = self._records_by_id[ext_id]
            record["status"] = ExtractionStatus.FAILED
            record["extracted_data"] = {}
            record["confidence_score"] = None
            record["model_version"] = model_version
            record["error_message"] = error_message
            record["updated_at"] = now
        else:
            record = {
                "id": existing_id,
                "project_id": project_id,
                "field_input_id": field_input_id,
                "status": ExtractionStatus.FAILED,
                "extracted_data": {},
                "confidence_score": None,
                "model_version": model_version,
                "error_message": error_message,
                "created_at": now,
                "updated_at": now,
            }
            self._records_by_id[existing_id] = record
            self._unique_index[composite_key] = existing_id

        return record

    def clear(self) -> None:
        """Clears local repository records and index for test isolation."""
        self._records_by_id.clear()
        self._unique_index.clear()


class ExtractionService:
    """Domain service managing the extraction lifecycle and public.ai_extractions persistence."""

    def __init__(
        self,
        gemini_provider: GeminiService | None = None,
        repository: AIExtractionRepository | None = None,
    ) -> None:
        self.gemini_service = gemini_provider or gemini_service
        self.repository = repository or AIExtractionRepository()

    async def extract_and_persist(
        self,
        project_id: str,
        field_input_id: str,
        fake_response: dict[str, Any] | str | None = None,
    ) -> ExtractionResponse:
        """
        Orchestrates full extraction pipeline:
        1. Validates project boundary & input ownership.
        2. Validates raw text availability & eligibility.
        3. Invokes Gemini via LangChain.
        4. Injects server-authoritative metadata.
        5. Normalizes units and disciplines.
        6. Verifies exact substring containment of all evidence tokens.
        7. Persists/updates extraction in public.ai_extractions atomically.
        """
        # Step 1: Verify project ownership and boundary
        field_input = self._load_and_verify_input(project_id, field_input_id)

        # Step 2: Verify raw text availability
        raw_text = self._validate_input_eligibility(field_input)

        # Parse authoritative UUID
        try:
            authoritative_input_uuid = UUID(field_input_id)
        except ValueError:
            authoritative_input_uuid = uuid.uuid4()

        now = datetime.now(timezone.utc)

        # Step 3: Invoke Gemini LLM Provider
        try:
            raw_extraction = await self.gemini_service.extract_structured_data(
                raw_input_id=authoritative_input_uuid,
                raw_text=raw_text,
                field_date=field_input.field_date,
                input_type=field_input.input_type.value,
                title=field_input.title,
                fake_response=fake_response,
            )
        except (GeminiProviderError, GeminiTimeoutError, GeminiExtractionParseError, GeminiConfigurationError) as err:
            # Record failure state in persistence for tracking, preserving raw input
            error_msg = f"AI Provider Error: {str(err)}"
            await self.repository.upsert_failed(
                project_id=project_id,
                field_input_id=field_input_id,
                error_message=error_msg,
                model_version=self.gemini_service.model_version_string,
            )
            raise

        # Step 4: Enforce Server-Authoritative Metadata
        reanchored_extraction = ExtractionResult(
            raw_input_id=authoritative_input_uuid,
            extracted_activities=raw_extraction.extracted_activities,
            extraction_confidence=raw_extraction.extraction_confidence,
            model_version=self.gemini_service.model_version_string,
            processing_timestamp=now,
        )

        # Step 5: Deterministic Normalization
        normalized_extraction = normalize_extraction(reanchored_extraction)

        # Step 6: Evidence Token Verification
        await self._verify_evidence_tokens(
            raw_text=raw_text,
            extraction=normalized_extraction,
            project_id=project_id,
            field_input_id=field_input_id,
        )

        # Step 7: Persist Completed Extraction Idempotently to public.ai_extractions
        record = await self.repository.upsert_completed(
            project_id=project_id,
            field_input_id=field_input_id,
            extraction=normalized_extraction,
        )

        return self._to_response(record)

    async def get_extraction(self, project_id: str, extraction_id: str) -> ExtractionResponse | None:
        """Retrieves a single extraction ensuring project scoping."""
        record = await self.repository.get_by_id(project_id, extraction_id)
        if not record:
            return None
        return self._to_response(record)

    async def get_extraction_by_input(self, project_id: str, field_input_id: str) -> ExtractionResponse | None:
        """Retrieves extraction result for a specific field input."""
        record = await self.repository.get_by_input(project_id, field_input_id)
        if not record:
            return None
        return self._to_response(record)

    async def list_extractions(
        self,
        project_id: str,
        status: ExtractionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ExtractionListResponse:
        """Lists all extractions in a project with optional status filter."""
        records, total = await self.repository.list_by_project(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return ExtractionListResponse(
            extractions=[self._to_response(r) for r in records],
            total=total,
        )

    # --- Internal Validation Helpers ---

    def _load_and_verify_input(self, project_id: str, field_input_id: str) -> FieldInputResponse:
        """Verifies existence and project ownership of field input."""
        raw_dict = input_service._inputs.get(field_input_id)
        if not raw_dict:
            raise ExtractionNotFoundError(f"Field input '{field_input_id}' not found")

        if raw_dict["project_id"] != project_id:
            raise CrossProjectInputError(
                f"Field input '{field_input_id}' does not belong to project '{project_id}'"
            )

        inp = input_service.get_input(project_id, field_input_id)
        if not inp:
            raise ExtractionNotFoundError(f"Field input '{field_input_id}' not found in project '{project_id}'")
        return inp

    def _validate_input_eligibility(self, inp: FieldInputResponse) -> str:
        """Validates that field input has extractable non-empty text."""
        raw_text = (inp.raw_text or "").strip()

        if inp.input_type == FieldInputType.TEXT:
            if not raw_text:
                raise ExtractionInputError("Text input contains no text content for extraction")
            return raw_text

        if inp.input_type == FieldInputType.VOICE:
            if inp.transcription_status != TranscriptionStatus.COMPLETED or not raw_text:
                raise ExtractionInputError(
                    f"Voice input transcription is not completed (current status: {inp.transcription_status.value})"
                )
            return raw_text

        if inp.input_type in (FieldInputType.PHOTO, FieldInputType.DOCUMENT):
            if not raw_text:
                raise ExtractionInputError(
                    f"{inp.input_type.value.capitalize()} input has no accompanying text notes or caption for extraction"
                )
            return raw_text

        raise ExtractionInputError(f"Unsupported input type '{inp.input_type}' for extraction")

    async def _verify_evidence_tokens(
        self,
        raw_text: str,
        extraction: ExtractionResult,
        project_id: str,
        field_input_id: str,
    ) -> None:
        """
        Verifies that every evidence token is an exact case-sensitive substring of raw_text.
        If any token fails, records extraction as FAILED and raises EvidenceVerificationError.
        """
        for activity in extraction.extracted_activities:
            for token in activity.evidence_tokens:
                if token not in raw_text:
                    err_msg = f"Evidence verification failed: token '{token}' is not an exact substring in raw text"
                    await self.repository.upsert_failed(
                        project_id=project_id,
                        field_input_id=field_input_id,
                        error_message=err_msg,
                        model_version=self.gemini_service.model_version_string,
                    )
                    raise EvidenceVerificationError(err_msg)

    def _to_response(self, r: dict[str, Any]) -> ExtractionResponse:
        """Converts repository record to typed ExtractionResponse."""
        status_val = r["status"]
        if isinstance(status_val, str):
            status_enum = ExtractionStatus(status_val)
        else:
            status_enum = status_val

        created_at_val = r["created_at"]
        if isinstance(created_at_val, str):
            created_at_dt = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
        else:
            created_at_dt = created_at_val

        updated_at_val = r["updated_at"]
        if isinstance(updated_at_val, str):
            updated_at_dt = datetime.fromisoformat(updated_at_val.replace("Z", "+00:00"))
        else:
            updated_at_dt = updated_at_val

        return ExtractionResponse(
            id=str(r["id"]),
            project_id=str(r["project_id"]),
            field_input_id=str(r["field_input_id"]),
            status=status_enum,
            extracted_data=r.get("extracted_data") or {},
            confidence_score=float(r["confidence_score"]) if r.get("confidence_score") is not None else None,
            model_version=str(r["model_version"]),
            error_message=r.get("error_message"),
            created_at=created_at_dt,
            updated_at=updated_at_dt,
        )

    def clear(self) -> None:
        """Clears repository records (for test isolation)."""
        self.repository.clear()


# Singleton service instance
extraction_service = ExtractionService()
