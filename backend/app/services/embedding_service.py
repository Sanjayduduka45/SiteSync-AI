"""
Vector Embedding Service — SiteSync AI Phase 6.4.
Generates 768-dimensional dense vector embeddings using Google text-embedding-004
via LangChain for schedule activities (retrieval_document) and extracted field progress (retrieval_query).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable, Sequence
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.schemas.schedule import (
    ActivityEmbeddingMetadata,
    ScheduleActivityCreate,
    ScheduleActivityResponse,
)

logger = logging.getLogger(__name__)

# Canonical Google Embedding Configuration
CANONICAL_EMBEDDING_MODEL = "models/gemini-embedding-001"
CANONICAL_EMBEDDING_DIMENSION = 768
TASK_TYPE_DOCUMENT = "retrieval_document"
TASK_TYPE_QUERY = "retrieval_query"


# Domain Exceptions
class EmbeddingError(Exception):
    """Base domain embedding exception."""


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when required embedding API keys or settings are missing."""


class EmbeddingProviderError(EmbeddingError):
    """Raised when upstream embedding provider fails or times out."""


class EmbeddingDimensionError(EmbeddingError):
    """Raised when embedding provider returns a vector with invalid dimensionality."""


def compute_content_hash(text: str) -> str:
    """Computes deterministic SHA-256 hex digest for canonical activity text."""
    if not isinstance(text, str):
        text = str(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_schedule_activity_embedding_text(
    activity: ScheduleActivityCreate | ScheduleActivityResponse | dict[str, Any],
) -> str:
    """
    Constructs deterministic canonical text from schedule activity attributes.
    Excludes non-semantic timestamps or database IDs.
    """
    if isinstance(activity, (ScheduleActivityCreate, ScheduleActivityResponse)):
        act_dict = activity.model_dump()
    elif isinstance(activity, dict):
        act_dict = activity
    else:
        raise ValueError("Unsupported activity type for canonical text construction")

    parts: list[str] = []

    name = act_dict.get("name")
    if name:
        parts.append(f"Activity: {str(name).strip()}")

    code = act_dict.get("activity_code")
    if code:
        parts.append(f"Code: {str(code).strip()}")

    discipline = act_dict.get("discipline")
    if discipline:
        parts.append(f"Discipline: {str(discipline).strip()}")

    wbs = act_dict.get("wbs_code")
    if wbs:
        parts.append(f"WBS: {str(wbs).strip()}")

    location = act_dict.get("location")
    if location:
        parts.append(f"Location: {str(location).strip()}")

    unit = act_dict.get("planned_unit")
    if unit:
        parts.append(f"Unit: {str(unit).strip()}")

    return "\n".join(parts)


def build_extracted_activity_query_text(
    description: str,
    discipline: str | None = None,
    location: str | None = None,
    unit: str | None = None,
) -> str:
    """
    Constructs deterministic canonical query text for an extracted field activity.
    """
    parts: list[str] = [f"Activity: {description.strip()}"]

    if discipline and discipline.strip():
        parts.append(f"Discipline: {discipline.strip()}")

    if location and location.strip():
        parts.append(f"Location: {location.strip()}")

    if unit and unit.strip():
        parts.append(f"Unit: {unit.strip()}")

    return "\n".join(parts)


def generate_deterministic_mock_embedding(
    text: str, dimension: int = CANONICAL_EMBEDDING_DIMENSION
) -> list[float]:
    """
    Generates a deterministic, unit-normalized float vector of length `dimension`
    seeded by the input text SHA-256 hash. Used for offline unit testing without external API calls.
    """
    if not text:
        text = "empty"

    raw_hash = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand seed deterministically to requested dimension
    floats: list[float] = []
    chunk_idx = 0
    current_seed = raw_hash

    while len(floats) < dimension:
        current_seed = hashlib.sha256(current_seed + chunk_idx.to_bytes(4, "big")).digest()
        for i in range(0, len(current_seed), 4):
            if len(floats) >= dimension:
                break
            val = int.from_bytes(current_seed[i : i + 4], "big", signed=True)
            floats.append(float(val) / 2147483648.0)
        chunk_idx += 1

    # L2 normalize
    norm = sum(x * x for x in floats) ** 0.5
    if norm > 0:
        floats = [x / norm for x in floats]

    return floats


class ActivityEmbeddingRepository:
    """
    Persistence repository for public.activity_embeddings.
    Uses PostgREST service-role client when configured, or an internal store for offline tests.
    """

    def __init__(self) -> None:
        # key: schedule_activity_id (str) -> dict
        self._embeddings: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._embeddings.clear()

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

    async def upsert_embedding(
        self,
        project_id: str,
        schedule_activity_id: str,
        embedding: list[float],
        content_hash: str,
    ) -> ActivityEmbeddingMetadata:
        """Upserts an activity embedding record ensuring project boundary scoping."""
        now = datetime.now(timezone.utc)
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/activity_embeddings"
            params = {"on_conflict": "schedule_activity_id"}
            payload = {
                "project_id": project_id,
                "schedule_activity_id": schedule_activity_id,
                "embedding": embedding,
                "content_hash": content_hash,
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
                            return self._row_to_metadata(rows[0])
            except Exception as err:
                logger.error(f"Failed to upsert activity embedding via PostgREST: {err}")

        # Local / in-memory store
        record = {
            "project_id": project_id,
            "schedule_activity_id": schedule_activity_id,
            "embedding": embedding,
            "content_hash": content_hash,
            "created_at": now,
            "updated_at": now,
        }
        self._embeddings[schedule_activity_id] = record
        return self._dict_to_metadata(record)

    async def get_embedding(
        self,
        project_id: str,
        schedule_activity_id: str,
    ) -> ActivityEmbeddingMetadata | None:
        """Retrieves embedding metadata for a schedule activity."""
        record = self._embeddings.get(schedule_activity_id)
        if record and record.get("project_id") == project_id:
            return self._dict_to_metadata(record)
        return None

    def _dict_to_metadata(self, record: dict[str, Any]) -> ActivityEmbeddingMetadata:
        return ActivityEmbeddingMetadata(
            schedule_activity_id=UUID(str(record["schedule_activity_id"])),
            project_id=UUID(str(record["project_id"])),
            content_hash=record["content_hash"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def _row_to_metadata(self, row: dict[str, Any]) -> ActivityEmbeddingMetadata:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return ActivityEmbeddingMetadata(
            schedule_activity_id=UUID(row["schedule_activity_id"]),
            project_id=UUID(row["project_id"]),
            content_hash=row["content_hash"],
            created_at=created_at,
            updated_at=updated_at,
        )


class EmbeddingService:
    """
    Isolated vector embedding provider service using Google GenAI / LangChain.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = CANONICAL_EMBEDDING_MODEL,
        dimension: int = CANONICAL_EMBEDDING_DIMENSION,
        mock_provider: Callable[..., Any] | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model
        self.dimension = dimension
        self._mock_provider = mock_provider
        self.repository = ActivityEmbeddingRepository()

    async def embed_document(self, text: str) -> list[float]:
        """
        Embeds a document text (e.g. schedule activity) with retrieval_document task type.
        """
        return await self._invoke_embedding(text, task_type=TASK_TYPE_DOCUMENT)

    async def embed_query(self, text: str) -> list[float]:
        """
        Embeds a query text (e.g. extracted field activity) with retrieval_query task type.
        """
        return await self._invoke_embedding(text, task_type=TASK_TYPE_QUERY)

    async def embed_schedule_activity(
        self,
        activity: ScheduleActivityCreate | ScheduleActivityResponse | dict[str, Any],
    ) -> tuple[list[float], str]:
        """
        Constructs canonical text, computes content hash, and generates document embedding.
        Returns: (embedding_vector, content_hash)
        """
        canonical_text = build_schedule_activity_embedding_text(activity)
        if not canonical_text.strip():
            raise ValueError("Schedule activity must contain at least a name or activity_code to embed")

        content_hash = compute_content_hash(canonical_text)
        vector = await self.embed_document(canonical_text)
        return vector, content_hash

    async def embed_extracted_activity(
        self,
        description: str,
        discipline: str | None = None,
        location: str | None = None,
        unit: str | None = None,
    ) -> list[float]:
        """
        Constructs canonical query text and generates query embedding.
        """
        query_text = build_extracted_activity_query_text(
            description=description,
            discipline=discipline,
            location=location,
            unit=unit,
        )
        return await self.embed_query(query_text)

    async def _invoke_embedding(self, text: str, task_type: str) -> list[float]:
        """Internal execution with dimension validation and secret-safe error handling."""
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty or whitespace-only text")

        vector: list[float]

        if self._mock_provider is not None:
            res = self._mock_provider(text, task_type)
            if hasattr(res, "__await__"):
                res = await res
            vector = list(res)
        else:
            if not self._api_key or not self._api_key.strip():
                raise EmbeddingConfigurationError("GEMINI_API_KEY is not configured on the backend server")

            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                embedder = GoogleGenerativeAIEmbeddings(
                    model=self.model,
                    google_api_key=self._api_key,
                    task_type=task_type,
                )
                vector = await embedder.aembed_query(text)
            except Exception as err:
                err_msg = re.sub(r"key=[^&\s]+", "key=[REDACTED]", str(err))
                logger.error(f"Google embedding API call failed: {err_msg}")
                raise EmbeddingProviderError(f"Embedding generation failed: {err_msg}") from err

        if len(vector) != self.dimension:
            raise EmbeddingDimensionError(
                f"Embedding provider returned vector of dimension {len(vector)}, expected {self.dimension}"
            )

        return vector


# Singleton instance
embedding_service = EmbeddingService()
