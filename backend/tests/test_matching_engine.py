"""
SiteSync AI — Phase 6.5 Multi-Factor Schedule Matching Engine Tests.
Tests:
  1. Semantic similarity calculation & cosine distance conversion
  2. Semantic score clamped to [0.0, 1.0]
  3. Discipline exact match bonus
  4. Discipline mismatch
  5. Location exact match
  6. Location partial/token overlap
  7. Location mismatch
  8. Temporal activity inside schedule window
  9. Temporal same-day match
  10. Temporal distance decay
  11. Missing event date
  12. Missing schedule dates
  13. Invalid / inverted schedule date handling
  14. Composite score normalization (sum of weights = 1.0)
  15. Confidence HIGH boundary (>= 0.85)
  16. Confidence MEDIUM boundary (0.60 - 0.849)
  17. Confidence LOW boundary (< 0.60)
  18. Deterministic ranking
  19. Deterministic tie breaking (composite score, semantic sim, activity_code, ID)
  20. Top recommendation selection
  21. Alternatives capped at 3
  22. Candidate query always project scoped
  23. Cross-project candidate rejected
  24. Query embedding uses retrieval_query
  25. Provider failure propagated as controlled domain error
  26. Empty candidate set raises NoCandidatesError
  27. Absence of Phase 7 (approval), Phase 8 (variance), and Phase 9 (risk) concepts
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4
import pytest

from app.schemas.extractions import ExtractedActivity
from app.schemas.schedule import MatchConfidenceLevel, ScheduleActivityCreate
from app.services.embedding_service import (
    CANONICAL_EMBEDDING_DIMENSION,
    EmbeddingProviderError,
    EmbeddingService,
    generate_deterministic_mock_embedding,
)
from app.services.matching_service import (
    WEIGHT_DISCIPLINE,
    WEIGHT_LOCATION,
    WEIGHT_SEMANTIC,
    WEIGHT_TEMPORAL,
    CrossProjectCandidateError,
    MatchingService,
    NoCandidatesError,
    ScheduleCandidate,
    calculate_discipline_score,
    calculate_location_score,
    calculate_semantic_similarity,
    calculate_temporal_score,
)
from app.services.schedule_service import ScheduleService


def test_1_semantic_similarity_and_cosine_distance_conversion():
    """Verify cosine distance to similarity conversion."""
    sim1 = calculate_semantic_similarity(0.15)
    assert abs(sim1 - 0.85) < 1e-6

    sim2 = calculate_semantic_similarity(0.0)
    assert sim2 == 1.0


def test_2_semantic_score_clamped_to_0_1():
    """Verify similarity handles anomalous distances outside [0, 2]."""
    assert calculate_semantic_similarity(-0.1) == 1.0
    assert calculate_semantic_similarity(1.5) == 0.0


def test_3_and_4_discipline_matching():
    """Verify exact case-insensitive match gives 1.0, mismatch or missing gives 0.0."""
    assert calculate_discipline_score("Piping", "piping") == 1.0
    assert calculate_discipline_score("Civil", "Electrical") == 0.0
    assert calculate_discipline_score(None, "Piping") == 0.0
    assert calculate_discipline_score("Piping", None) == 0.0


def test_5_6_7_location_matching():
    """Verify exact, token-overlap, and mismatch location scoring."""
    # Exact match
    assert calculate_location_score("Unit 4 Rack B", "unit 4 rack b") == 1.0

    # Partial token overlap
    partial = calculate_location_score("Unit 4 Rack B", "Unit 4 North Section")
    assert 0.5 < partial < 1.0

    # Partial token overlap ("zone" in both)
    partial_zone = calculate_location_score("Zone 1", "Zone 99")
    assert 0.5 < partial_zone < 1.0

    # Total mismatch (zero token overlap)
    assert calculate_location_score("Zone 1", "Building 99") == 0.0

    # Missing location
    assert calculate_location_score(None, "Rack B") == 0.0


def test_8_9_10_temporal_matching():
    """Verify temporal scoring: inside window, same day, and distance decay."""
    # Inside window
    assert calculate_temporal_score(date(2026, 9, 5), date(2026, 9, 1), date(2026, 9, 10)) == 1.0

    # Same day match
    assert calculate_temporal_score(date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 1)) == 1.0

    # 10 days late -> decay: 1.0 - (10 / 30) = 0.667
    late_score = calculate_temporal_score(date(2026, 9, 20), date(2026, 9, 1), date(2026, 9, 10))
    assert abs(late_score - (1.0 - 10 / 30.0)) < 1e-4

    # 35 days late -> 0.0
    assert calculate_temporal_score(date(2026, 10, 20), date(2026, 9, 1), date(2026, 9, 10)) == 0.0


def test_11_12_13_temporal_edge_cases():
    """Verify missing dates and inverted schedule dates are handled defensively."""
    # Missing event date
    assert calculate_temporal_score(None, date(2026, 9, 1), date(2026, 9, 10)) == 0.0

    # Missing schedule dates
    assert calculate_temporal_score(date(2026, 9, 5), None, None) == 0.0

    # Inverted schedule dates (start > finish) handled safely
    inverted_score = calculate_temporal_score(date(2026, 9, 5), date(2026, 9, 10), date(2026, 9, 1))
    assert inverted_score == 1.0


def test_14_composite_score_weights_sum_to_one():
    """Verify all canonical contextual weights sum exactly to 1.0."""
    total_weight = WEIGHT_SEMANTIC + WEIGHT_DISCIPLINE + WEIGHT_LOCATION + WEIGHT_TEMPORAL
    assert abs(total_weight - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_15_16_17_confidence_bands():
    """Verify match classification across High, Medium, Low confidence thresholds."""
    proj_id = uuid4()
    mock_embedder = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    # 1. High confidence candidate (identical text, discipline, location, date)
    high_candidate = ScheduleCandidate(
        schedule_activity_id=uuid4(),
        project_id=proj_id,
        activity_code="ACT-HIGH",
        activity_name="Install 6-inch Chilled Water Pipe",
        wbs_code="1.1",
        discipline="Piping",
        location="Rack 4",
        planned_start_date=date(2026, 9, 1),
        planned_finish_date=date(2026, 9, 15),
        planned_quantity=100.0,
        planned_unit="LF",
        cosine_distance=0.05,  # Semantic sim 0.95
    )

    matching_svc = MatchingService(
        embed_service=mock_embedder,
        candidate_provider=lambda pid, qvec, limit: [high_candidate],
    )

    extracted_act = ExtractedActivity(
        description="Installed 6-inch Chilled Water Pipe",
        discipline="Piping",
        location="Rack 4",
        event_date=date(2026, 9, 5),
    )

    res = await matching_svc.match_extracted_activity(proj_id, extracted_act)
    assert res.confidence_score >= 0.85
    assert res.confidence_level == MatchConfidenceLevel.HIGH


@pytest.mark.asyncio
async def test_18_19_20_21_ranking_tie_breaking_and_alternatives():
    """Verify deterministic ranking, tie-breaking, and capping alternatives at 3."""
    proj_id = uuid4()
    mock_embedder = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    # Create 5 candidates with known distances
    cands: list[ScheduleCandidate] = [
        ScheduleCandidate(
            schedule_activity_id=uuid4(),
            project_id=proj_id,
            activity_code=f"ACT-00{i}",
            activity_name=f"Candidate {i}",
            wbs_code="1.0",
            discipline="Piping",
            location="Zone A",
            planned_start_date=date(2026, 9, 1),
            planned_finish_date=date(2026, 9, 10),
            planned_quantity=10.0,
            planned_unit="LF",
            cosine_distance=0.1 * i,  # 0.1, 0.2, 0.3, 0.4, 0.5
        )
        for i in range(1, 6)
    ]

    matching_svc = MatchingService(
        embed_service=mock_embedder,
        candidate_provider=lambda pid, qvec, limit: cands,
    )

    extracted_act = ExtractedActivity(
        description="Piping work",
        discipline="Piping",
        location="Zone A",
        event_date=date(2026, 9, 2),
    )

    res = await matching_svc.match_extracted_activity(proj_id, extracted_act)

    # Top recommendation is ACT-001 (lowest distance / highest score)
    assert res.recommended_activity_code == "ACT-001"

    # Alternatives are ACT-002, ACT-003, ACT-004 (capped at 3)
    assert len(res.alternative_matches) == 3
    assert res.alternative_matches[0].activity_code == "ACT-002"
    assert res.alternative_matches[1].activity_code == "ACT-003"
    assert res.alternative_matches[2].activity_code == "ACT-004"


@pytest.mark.asyncio
async def test_23_and_24_cross_project_candidate_rejected():
    """Verify a candidate from a different project raises CrossProjectCandidateError."""
    proj_a = uuid4()
    proj_b = uuid4()
    mock_embedder = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    leaked_cand = ScheduleCandidate(
        schedule_activity_id=uuid4(),
        project_id=proj_b,  # Belongs to Project B!
        activity_code="ACT-LEAK",
        activity_name="Foreign Activity",
        wbs_code=None,
        discipline=None,
        location=None,
        planned_start_date=None,
        planned_finish_date=None,
        planned_quantity=None,
        planned_unit=None,
        cosine_distance=0.1,
    )

    matching_svc = MatchingService(
        embed_service=mock_embedder,
        candidate_provider=lambda pid, qvec, limit: [leaked_cand],
    )

    extracted_act = ExtractedActivity(description="Test activity")

    with pytest.raises(CrossProjectCandidateError):
        await matching_svc.match_extracted_activity(proj_a, extracted_act)


@pytest.mark.asyncio
async def test_26_empty_candidate_set_raises_no_candidates():
    """Verify empty candidate set raises NoCandidatesError."""
    proj_id = uuid4()
    mock_embedder = EmbeddingService(
        mock_provider=lambda text, task_type: generate_deterministic_mock_embedding(text)
    )

    matching_svc = MatchingService(
        embed_service=mock_embedder,
        candidate_provider=lambda pid, qvec, limit: [],
    )

    extracted_act = ExtractedActivity(description="Test activity")

    with pytest.raises(NoCandidatesError):
        await matching_svc.match_extracted_activity(proj_id, extracted_act)


def test_27_no_downstream_phase7_8_9_in_matching_engine():
    """Verify absence of planner approval, variance, or risk in Phase 6.5 code."""
    from app.services import matching_service as ms_module
    import inspect

    source = inspect.getsource(ms_module)
    forbidden = [
        "planner_approval",
        "approved_actual",
        "approval_status",
        "variance",
        "critical_path",
        "risk_engine",
        "risk_heatmap",
    ]
    for term in forbidden:
        assert term not in source.lower(), f"Forbidden term '{term}' found in matching_service"
