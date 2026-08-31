"""
Multi-Factor Schedule Matching Engine — SiteSync AI Phase 6.5.
Matches extracted construction progress activities to baseline schedule activities
using pgvector cosine similarity search and multi-factor contextual re-ranking
(discipline match, location overlap, temporal proximity) with strict tenant isolation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional, Sequence
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.schemas.extractions import ExtractedActivity
from app.schemas.schedule import (
    AlternativeMatch,
    MatchConfidenceLevel,
    MatchRecommendationResponse,
    ScoringBreakdown,
)
from app.services.embedding_service import (
    CANONICAL_EMBEDDING_DIMENSION,
    EmbeddingService,
    embedding_service,
)
from app.services.schedule_service import ScheduleService, schedule_service

logger = logging.getLogger(__name__)

# Canonical Contextual Scoring Weights (sum = 1.00)
# Documented implementation defaults for SiteSync AI Phase 6.5
WEIGHT_SEMANTIC = 0.70
WEIGHT_DISCIPLINE = 0.15
WEIGHT_LOCATION = 0.10
WEIGHT_TEMPORAL = 0.05

# Candidate Retrieval Limits
MAX_CANDIDATES_RETRIEVAL = 10
MAX_ALTERNATIVE_MATCHES = 3


# Domain Exceptions
class MatchingError(Exception):
    """Base domain matching exception."""


class NoCandidatesError(MatchingError):
    """Raised when no schedule activity candidates exist for the project."""


class CrossProjectCandidateError(MatchingError):
    """Raised when a retrieved candidate does not belong to the requested project."""


@dataclass(frozen=True)
class ScheduleCandidate:
    """Schedule activity candidate with raw vector distance."""
    schedule_activity_id: UUID
    project_id: UUID
    activity_code: str
    activity_name: str
    wbs_code: Optional[str]
    discipline: Optional[str]
    location: Optional[str]
    planned_start_date: Optional[date]
    planned_finish_date: Optional[date]
    planned_quantity: Optional[float]
    planned_unit: Optional[str]
    cosine_distance: float


def calculate_semantic_similarity(cosine_distance: float) -> float:
    """Converts raw cosine distance to similarity score clamped to [0.0, 1.0]."""
    raw_sim = 1.0 - float(cosine_distance)
    return max(0.0, min(1.0, raw_sim))


def calculate_discipline_score(
    source_discipline: Optional[str],
    candidate_discipline: Optional[str],
) -> float:
    """Exact case-insensitive match for construction trade disciplines."""
    if not source_discipline or not candidate_discipline:
        return 0.0
    if source_discipline.strip().lower() == candidate_discipline.strip().lower():
        return 1.0
    return 0.0


def calculate_location_score(
    source_location: Optional[str],
    candidate_location: Optional[str],
) -> float:
    """Deterministic exact or token-overlap matching for physical site locations."""
    if not source_location or not candidate_location:
        return 0.0

    src = source_location.strip().lower()
    cand = candidate_location.strip().lower()

    if src == cand:
        return 1.0

    # Token overlap with min token length 2
    src_tokens = {t for t in re_split_tokens(src) if len(t) >= 2}
    cand_tokens = {t for t in re_split_tokens(cand) if len(t) >= 2}

    if not src_tokens or not cand_tokens:
        return 0.0

    intersection = src_tokens.intersection(cand_tokens)
    if not intersection:
        return 0.0

    overlap_ratio = len(intersection) / max(len(src_tokens), len(cand_tokens))
    return min(1.0, 0.5 + 0.5 * overlap_ratio)


def calculate_temporal_score(
    event_date: Optional[date],
    planned_start: Optional[date],
    planned_finish: Optional[date],
) -> float:
    """
    Evaluates temporal alignment between extracted field event date and planned schedule window.
    Full score if within window; linear decay over 30 days if outside.
    """
    if not event_date or (not planned_start and not planned_finish):
        return 0.0

    # Defensively handle missing one-sided dates or inverted dates
    start = planned_start or planned_finish
    finish = planned_finish or planned_start

    if start and finish and start > finish:
        start, finish = finish, start

    assert start is not None and finish is not None

    if start <= event_date <= finish:
        return 1.0

    if event_date < start:
        day_diff = (start - event_date).days
    else:
        day_diff = (event_date - finish).days

    # Linear decay over 30 days
    if day_diff >= 30:
        return 0.0
    return max(0.0, 1.0 - (day_diff / 30.0))


def re_split_tokens(text: str) -> list[str]:
    """Helper to split string into alphanumeric words."""
    import re
    return re.findall(r"\w+", text)


def _parse_uuid(val: Any) -> UUID:
    """Safely converts string or UUID to UUID object, resolving non-hex strings deterministically."""
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        import uuid
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


class MatchingService:
    """
    Multi-Factor Schedule Matching Engine.
    Executes semantic similarity search and contextual re-ranking within strict project boundaries.
    """

    def __init__(
        self,
        embed_service: Optional[EmbeddingService] = None,
        sched_service: Optional[ScheduleService] = None,
        candidate_provider: Optional[Callable[..., Any]] = None,
        repository: Optional[AIMatchRepository] = None,
    ) -> None:
        self.embedding_service = embed_service or embedding_service
        self.schedule_service = sched_service or schedule_service
        self._candidate_provider = candidate_provider
        self.repository = repository or AIMatchRepository()

    async def match_extracted_activity(
        self,
        project_id: str | UUID,
        activity: ExtractedActivity,
        extraction_id: Optional[UUID] = None,
        activity_index: int = 0,
    ) -> MatchRecommendationResponse:
        """
        Main matching entry point for an ExtractedActivity.
        Generates query embedding, retrieves project-scoped candidates, scores, and re-ranks.
        """
        proj_uuid = _parse_uuid(project_id)
        ext_uuid = _parse_uuid(extraction_id) if extraction_id else uuid4()

        # 1. Generate query vector using retrieval_query task type
        query_vector = await self.embedding_service.embed_extracted_activity(
            description=activity.description,
            discipline=activity.discipline,
            location=activity.location,
            unit=activity.progress_unit,
        )

        # 2. Retrieve top candidates strictly scoped to project_id
        candidates = await self._retrieve_candidates(proj_uuid, query_vector, limit=MAX_CANDIDATES_RETRIEVAL)
        if not candidates:
            raise NoCandidatesError(f"No schedule activities available for project '{proj_uuid}'")

        # 3. Contextual re-ranking
        ranked = self._score_and_rank_candidates(
            candidates=candidates,
            event_date=activity.event_date,
            source_discipline=activity.discipline,
            source_location=activity.location,
            requested_project_id=proj_uuid,
        )

        top_candidate, top_score, top_breakdown = ranked[0]

        # 4. Format alternative matches (capped at 3)
        alt_matches: list[AlternativeMatch] = []
        for alt_cand, alt_score, alt_breakdown in ranked[1 : 1 + MAX_ALTERNATIVE_MATCHES]:
            alt_matches.append(
                AlternativeMatch(
                    schedule_activity_id=alt_cand.schedule_activity_id,
                    activity_code=alt_cand.activity_code,
                    activity_name=alt_cand.activity_name,
                    confidence_score=round(alt_score, 3),
                    discipline=alt_cand.discipline,
                    location=alt_cand.location,
                    planned_start_date=alt_cand.planned_start_date,
                    planned_finish_date=alt_cand.planned_finish_date,
                    scoring_breakdown=alt_breakdown,
                )
            )

        now = datetime.now(timezone.utc)
        return MatchRecommendationResponse(
            id=uuid4(),
            project_id=proj_uuid,
            extraction_id=ext_uuid,
            activity_index=activity_index,
            recommended_activity_id=top_candidate.schedule_activity_id,
            recommended_activity_code=top_candidate.activity_code,
            recommended_activity_name=top_candidate.activity_name,
            confidence_score=round(top_score, 3),
            scoring_breakdown=top_breakdown,
            alternative_matches=alt_matches,
            created_at=now,
            updated_at=now,
        )

    def _score_and_rank_candidates(
        self,
        candidates: Sequence[ScheduleCandidate],
        event_date: Optional[date],
        source_discipline: Optional[str],
        source_location: Optional[str],
        requested_project_id: UUID,
    ) -> list[tuple[ScheduleCandidate, float, ScoringBreakdown]]:
        """Scores all candidates and sorts them deterministically."""
        scored_candidates: list[tuple[ScheduleCandidate, float, ScoringBreakdown]] = []

        for cand in candidates:
            # Strict tenant boundary verification
            if cand.project_id != requested_project_id:
                raise CrossProjectCandidateError(
                    f"Candidate activity '{cand.schedule_activity_id}' belongs to project "
                    f"'{cand.project_id}', not requested project '{requested_project_id}'"
                )

            # A. Semantic similarity
            semantic_sim = calculate_semantic_similarity(cand.cosine_distance)

            # B. Discipline contribution
            disc_score = calculate_discipline_score(source_discipline, cand.discipline)

            # C. Location contribution
            loc_score = calculate_location_score(source_location, cand.location)

            # D. Temporal contribution
            temp_score = calculate_temporal_score(
                event_date=event_date,
                planned_start=cand.planned_start_date,
                planned_finish=cand.planned_finish_date,
            )

            # Composite normalized score
            composite_score = (
                semantic_sim * WEIGHT_SEMANTIC
                + disc_score * WEIGHT_DISCIPLINE
                + loc_score * WEIGHT_LOCATION
                + temp_score * WEIGHT_TEMPORAL
            )
            composite_score = max(0.0, min(1.0, composite_score))

            breakdown = ScoringBreakdown(
                semantic_similarity=round(semantic_sim, 3),
                discipline_contribution=round(disc_score * WEIGHT_DISCIPLINE, 3),
                location_contribution=round(loc_score * WEIGHT_LOCATION, 3),
                temporal_contribution=round(temp_score * WEIGHT_TEMPORAL, 3),
            )

            scored_candidates.append((cand, composite_score, breakdown))

        # Deterministic sort:
        # 1. Composite confidence descending
        # 2. Semantic similarity descending
        # 3. Activity code ascending
        # 4. Activity ID ascending
        scored_candidates.sort(
            key=lambda item: (
                -item[1],
                -item[2].semantic_similarity,
                item[0].activity_code,
                str(item[0].schedule_activity_id),
            )
        )

        return scored_candidates

    async def _retrieve_candidates(
        self,
        project_id: UUID,
        query_vector: list[float],
        limit: int = MAX_CANDIDATES_RETRIEVAL,
    ) -> list[ScheduleCandidate]:
        """
        Executes project-scoped similarity search against schedule activity embeddings.
        """
        if self._candidate_provider is not None:
            res = self._candidate_provider(project_id, query_vector, limit)
            if hasattr(res, "__await__"):
                res = await res
            return list(res)

        settings = get_settings()
        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/rpc/match_schedule_activities"
            payload = {
                "p_project_id": str(project_id),
                "p_query_embedding": query_vector,
                "p_match_count": limit,
            }
            key = settings.supabase_service_role_key or settings.supabase_anon_key
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        rows = resp.json()
                        candidates = []
                        for r in rows:
                            candidates.append(
                                ScheduleCandidate(
                                    schedule_activity_id=UUID(r["id"]),
                                    project_id=UUID(r["project_id"]),
                                    activity_code=r["activity_code"],
                                    activity_name=r["name"],
                                    wbs_code=r.get("wbs_code"),
                                    discipline=r.get("discipline"),
                                    location=r.get("location"),
                                    planned_start_date=r.get("planned_start_date"),
                                    planned_finish_date=r.get("planned_finish_date"),
                                    planned_quantity=r.get("planned_quantity"),
                                    planned_unit=r.get("planned_unit"),
                                    cosine_distance=float(r["distance"]),
                                )
                            )
                        return candidates
            except Exception as err:
                logger.error(f"PostgREST vector match RPC query failed: {err}")

        # In-memory test store scan
        candidates: list[ScheduleCandidate] = []
        for act_id, act_dict in self.schedule_service._activities.items():
            if _parse_uuid(act_dict.get("project_id")) == _parse_uuid(project_id):
                emb_meta = self.embedding_service.repository._embeddings.get(act_id)
                emb_vec = emb_meta.get("embedding") if emb_meta else None
                if not emb_vec:
                    # Deterministic mock embedding for test schedule activities
                    from app.services.embedding_service import generate_deterministic_mock_embedding
                    emb_vec = generate_deterministic_mock_embedding(act_dict["name"])

                # Cosine distance = 1 - (dot_product / (norm1 * norm2))
                dot_prod = sum(a * b for a, b in zip(query_vector, emb_vec))
                norm_q = math.sqrt(sum(a * a for a in query_vector)) or 1.0
                norm_e = math.sqrt(sum(b * b for b in emb_vec)) or 1.0
                cosine_sim = dot_prod / (norm_q * norm_e)
                cosine_dist = max(0.0, 1.0 - cosine_sim)

                candidates.append(
                    ScheduleCandidate(
                        schedule_activity_id=_parse_uuid(act_id),
                        project_id=_parse_uuid(act_dict["project_id"]),
                        activity_code=act_dict["activity_code"],
                        activity_name=act_dict["name"],
                        wbs_code=act_dict.get("wbs_code"),
                        discipline=act_dict.get("discipline"),
                        location=act_dict.get("location"),
                        planned_start_date=act_dict.get("planned_start_date"),
                        planned_finish_date=act_dict.get("planned_finish_date"),
                        planned_quantity=act_dict.get("planned_quantity"),
                        planned_unit=act_dict.get("planned_unit"),
                        cosine_distance=cosine_dist,
                    )
                )

        candidates.sort(key=lambda c: c.cosine_distance)
        return candidates[:limit]


class AIMatchRepository:
    """
    Database persistence repository for public.ai_matches.
    Enforces atomic upsert on (project_id, extraction_id, activity_index).
    """

    def __init__(self) -> None:
        # key: (project_id, extraction_id, activity_index) -> dict
        self._matches: dict[tuple[str, str, int], dict[str, Any]] = {}

    def clear(self) -> None:
        self._matches.clear()

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

    async def upsert_match(
        self,
        match: MatchRecommendationResponse,
    ) -> MatchRecommendationResponse:
        """Persists or updates an AI match recommendation record."""
        now = datetime.now(timezone.utc)
        settings = get_settings()
        proj_str = str(_parse_uuid(match.project_id))
        ext_str = str(_parse_uuid(match.extraction_id))

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_matches"
            params = {"on_conflict": "project_id,extraction_id,activity_index"}
            payload = {
                "project_id": proj_str,
                "extraction_id": ext_str,
                "activity_index": match.activity_index,
                "recommended_activity_id": str(match.recommended_activity_id),
                "confidence_score": match.confidence_score,
                "scoring_breakdown": match.scoring_breakdown.model_dump(),
                "alternative_matches": [alt.model_dump(mode="json") for alt in match.alternative_matches],
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
                logger.error(f"Failed to upsert ai_matches via PostgREST: {err}")

        # Local test store
        key = (proj_str, ext_str, match.activity_index)
        record = {
            "id": match.id,
            "project_id": match.project_id,
            "extraction_id": match.extraction_id,
            "activity_index": match.activity_index,
            "recommended_activity_id": match.recommended_activity_id,
            "recommended_activity_code": match.recommended_activity_code,
            "recommended_activity_name": match.recommended_activity_name,
            "confidence_score": match.confidence_score,
            "scoring_breakdown": match.scoring_breakdown,
            "alternative_matches": match.alternative_matches,
            "created_at": match.created_at or now,
            "updated_at": now,
        }
        self._matches[key] = record
        return match

    async def list_matches(
        self,
        project_id: str | UUID,
        extraction_id: str | UUID,
    ) -> list[MatchRecommendationResponse]:
        """Lists match recommendations for an extraction, strictly scoped to project_id."""
        proj_str = str(_parse_uuid(project_id))
        ext_str = str(_parse_uuid(extraction_id))
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_matches"
            params = {
                "project_id": f"eq.{proj_str}",
                "extraction_id": f"eq.{ext_str}",
                "select": "*,recommended_activity:schedule_activities(activity_code,name)",
                "order": "activity_index.asc",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        return [self._row_to_response(r) for r in rows]
            except Exception as err:
                logger.error(f"Failed to query ai_matches via PostgREST: {err}")

        # Local store
        results = [
            self._dict_to_response(rec)
            for key, rec in self._matches.items()
            if key[0] == proj_str and key[1] == ext_str
        ]
        results.sort(key=lambda m: m.activity_index)
        return results

    async def get_match(
        self,
        project_id: str | UUID,
        match_id: str | UUID,
    ) -> Optional[MatchRecommendationResponse]:
        """Retrieves a single match recommendation by ID, strictly scoped to project_id."""
        proj_str = str(_parse_uuid(project_id))
        match_str = str(_parse_uuid(match_id))
        settings = get_settings()

        if settings.supabase_url and settings.supabase_service_role_key and not settings.is_development:
            url = f"{settings.supabase_url}/rest/v1/ai_matches"
            params = {
                "project_id": f"eq.{proj_str}",
                "id": f"eq.{match_str}",
                "select": "*,recommended_activity:schedule_activities(activity_code,name)",
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(url, headers=self._get_supabase_headers(), params=params)
                    if resp.status_code == 200:
                        rows = resp.json()
                        if rows:
                            return self._row_to_response(rows[0])
            except Exception as err:
                logger.error(f"Failed to query ai_matches via PostgREST: {err}")

        # Local store
        for rec in self._matches.values():
            if str(rec["project_id"]) == proj_str and str(rec["id"]) == match_str:
                return self._dict_to_response(rec)
        return None

    def _dict_to_response(self, rec: dict[str, Any]) -> MatchRecommendationResponse:
        sb = rec["scoring_breakdown"]
        if not isinstance(sb, ScoringBreakdown):
            sb = ScoringBreakdown(**sb)

        return MatchRecommendationResponse(
            id=_parse_uuid(rec["id"]),
            project_id=_parse_uuid(rec["project_id"]),
            extraction_id=_parse_uuid(rec["extraction_id"]),
            activity_index=rec["activity_index"],
            recommended_activity_id=_parse_uuid(rec["recommended_activity_id"]),
            recommended_activity_code=rec.get("recommended_activity_code"),
            recommended_activity_name=rec.get("recommended_activity_name"),
            confidence_score=rec["confidence_score"],
            scoring_breakdown=sb,
            alternative_matches=rec.get("alternative_matches", []),
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
        )

    def _row_to_response(self, row: dict[str, Any]) -> MatchRecommendationResponse:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        updated_at = row["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        rec_activity = row.get("recommended_activity") or {}
        code = rec_activity.get("activity_code") if isinstance(rec_activity, dict) else None
        name = rec_activity.get("name") if isinstance(rec_activity, dict) else None

        alts = [
            AlternativeMatch(**alt) if isinstance(alt, dict) else alt
            for alt in row.get("alternative_matches", [])
        ]

        return MatchRecommendationResponse(
            id=_parse_uuid(row["id"]),
            project_id=_parse_uuid(row["project_id"]),
            extraction_id=_parse_uuid(row["extraction_id"]),
            activity_index=row["activity_index"],
            recommended_activity_id=_parse_uuid(row["recommended_activity_id"]),
            recommended_activity_code=code,
            recommended_activity_name=name,
            confidence_score=float(row["confidence_score"]),
            scoring_breakdown=ScoringBreakdown(**row.get("scoring_breakdown", {"semantic_similarity": 0.0})),
            alternative_matches=alts,
            created_at=created_at,
            updated_at=updated_at,
        )


# Singleton instance
matching_service = MatchingService()
matching_service.repository = AIMatchRepository()
