"""
SiteSync AI — Phase 6.2 Schedule and Matching Schema Tests.
Tests:
  1. Valid schedule activity creation
  2. Blank activity_code rejected
  3. Blank name rejected
  4. Negative planned_quantity rejected
  5. Invalid date ordering rejected
  6. Valid nullable schedule fields
  7. Metadata must be an object
  8. Valid schedule response
  9. Valid alternative match
  10. Invalid UUID rejected
  11. Confidence < 0 rejected
  12. Confidence > 1 rejected
  13. Valid confidence boundaries and confidence_level property
  14. Valid scoring breakdown
  15. Unknown fields rejected (extra='forbid')
  16. Phase 7 approval fields rejected
  17. Phase 8 variance fields rejected
  18. Phase 9 risk fields rejected
  19. Match list remains strongly typed
  20. Embedding metadata uses UUIDs and hash strings
  21. No embedding vector is exposed through public response schema
  22. Serialization and deserialization round trip
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError

from app.schemas.schedule import (
    ActivityEmbeddingMetadata,
    AlternativeMatch,
    MatchConfidenceLevel,
    MatchRecommendationListResponse,
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScheduleActivityListResponse,
    ScheduleActivityResponse,
    ScoringBreakdown,
)


def test_1_valid_schedule_activity_create():
    """Verify valid schedule activity creation model."""
    data = ScheduleActivityCreate(
        activity_code="ACT-1001",
        name="Install Pipe Spools Unit 4",
        wbs_code="1.2.4.1",
        discipline="Piping",
        location="Unit 4 Rack B",
        planned_start_date=date(2026, 9, 1),
        planned_finish_date=date(2026, 9, 15),
        planned_quantity=150.5,
        planned_unit="LF",
        metadata={"priority": "high", "crew": "Alpha"},
    )
    assert data.activity_code == "ACT-1001"
    assert data.name == "Install Pipe Spools Unit 4"
    assert data.planned_quantity == 150.5
    assert data.metadata["crew"] == "Alpha"


def test_2_blank_activity_code_rejected():
    """Verify blank activity_code raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        ScheduleActivityCreate(activity_code="   ", name="Valid Name")
    assert "activity_code" in str(exc.value)


def test_3_blank_name_rejected():
    """Verify blank name raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        ScheduleActivityCreate(activity_code="ACT-101", name="")
    assert "name" in str(exc.value)


def test_4_negative_planned_quantity_rejected():
    """Verify planned_quantity < 0 raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        ScheduleActivityCreate(activity_code="ACT-101", name="Valid Name", planned_quantity=-10.0)
    assert "planned_quantity" in str(exc.value)


def test_5_invalid_date_ordering_rejected():
    """Verify planned_start_date > planned_finish_date raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        ScheduleActivityCreate(
            activity_code="ACT-101",
            name="Valid Name",
            planned_start_date=date(2026, 9, 20),
            planned_finish_date=date(2026, 9, 10),
        )
    assert "planned_start_date" in str(exc.value)


def test_6_valid_nullable_schedule_fields():
    """Verify optional fields default to None or empty dict."""
    data = ScheduleActivityCreate(activity_code="ACT-102", name="Minimal Activity")
    assert data.wbs_code is None
    assert data.discipline is None
    assert data.location is None
    assert data.planned_start_date is None
    assert data.planned_finish_date is None
    assert data.planned_quantity is None
    assert data.planned_unit is None
    assert data.metadata == {}


def test_7_metadata_must_be_an_object():
    """Verify non-dictionary metadata is rejected."""
    with pytest.raises(ValidationError):
        ScheduleActivityCreate(activity_code="ACT-101", name="Valid Name", metadata="invalid_string")


def test_8_valid_schedule_response():
    """Verify ScheduleActivityResponse validation and attributes."""
    act_id = uuid4()
    proj_id = uuid4()
    now = datetime.now(timezone.utc)
    res = ScheduleActivityResponse(
        id=act_id,
        project_id=proj_id,
        activity_code="ACT-200",
        name="Electrical Conduit Run",
        discipline="Electrical",
        created_at=now,
        updated_at=now,
    )
    assert res.id == act_id
    assert res.project_id == proj_id
    assert res.activity_code == "ACT-200"


def test_9_valid_alternative_match():
    """Verify AlternativeMatch schema attributes."""
    act_id = uuid4()
    alt = AlternativeMatch(
        schedule_activity_id=act_id,
        activity_code="ACT-300",
        activity_name="Secondary Cable Tray Pull",
        confidence_score=0.72,
        discipline="Electrical",
        scoring_breakdown=ScoringBreakdown(
            semantic_similarity=0.70,
            discipline_contribution=0.80,
            location_contribution=0.50,
            temporal_contribution=0.90,
        ),
    )
    assert alt.schedule_activity_id == act_id
    assert alt.confidence_score == 0.72
    assert alt.scoring_breakdown.semantic_similarity == 0.70


def test_10_invalid_uuid_rejected():
    """Verify invalid UUID string raises ValidationError."""
    with pytest.raises(ValidationError):
        ScheduleActivityResponse(
            id="not-a-valid-uuid",
            project_id=uuid4(),
            activity_code="ACT-1",
            name="Name",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


def test_11_confidence_less_than_zero_rejected():
    """Verify confidence < 0.0 is rejected."""
    with pytest.raises(ValidationError):
        ScoringBreakdown(semantic_similarity=-0.05)


def test_12_confidence_greater_than_one_rejected():
    """Verify confidence > 1.0 is rejected."""
    with pytest.raises(ValidationError):
        ScoringBreakdown(semantic_similarity=1.05)


def test_13_valid_confidence_boundaries_and_property():
    """Verify confidence band classifications (High >= 0.85, Medium 0.60-0.849, Low < 0.60)."""
    now = datetime.now(timezone.utc)
    base_kwargs = dict(
        id=uuid4(),
        project_id=uuid4(),
        extraction_id=uuid4(),
        recommended_activity_id=uuid4(),
        created_at=now,
        updated_at=now,
    )

    high_match = MatchRecommendationResponse(confidence_score=0.85, **base_kwargs)
    assert high_match.confidence_level == MatchConfidenceLevel.HIGH

    med_match = MatchRecommendationResponse(confidence_score=0.60, **base_kwargs)
    assert med_match.confidence_level == MatchConfidenceLevel.MEDIUM

    low_match = MatchRecommendationResponse(confidence_score=0.59, **base_kwargs)
    assert low_match.confidence_level == MatchConfidenceLevel.LOW


def test_14_valid_scoring_breakdown():
    """Verify ScoringBreakdown validation."""
    sb = ScoringBreakdown(
        semantic_similarity=0.88,
        discipline_contribution=1.0,
        location_contribution=0.75,
        temporal_contribution=0.90,
    )
    assert sb.semantic_similarity == 0.88
    assert sb.discipline_contribution == 1.0


def test_15_unknown_fields_rejected_extra_forbid():
    """Verify extra='forbid' rejects arbitrary unknown fields."""
    with pytest.raises(ValidationError) as exc:
        ScheduleActivityCreate(
            activity_code="ACT-101",
            name="Valid Name",
            unauthorized_field="malicious_payload",
        )
    assert "extra_forbidden" in str(exc.value) or "unauthorized_field" in str(exc.value)


def test_16_phase7_approval_fields_rejected():
    """Verify Phase 7 approval fields are rejected by schemas."""
    with pytest.raises(ValidationError):
        MatchRecommendationResponse(
            id=uuid4(),
            project_id=uuid4(),
            extraction_id=uuid4(),
            recommended_activity_id=uuid4(),
            confidence_score=0.9,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            approved_actual_id=uuid4(),  # Phase 7 field
        )


def test_17_phase8_variance_fields_rejected():
    """Verify Phase 8 variance fields are rejected by schemas."""
    with pytest.raises(ValidationError):
        ScheduleActivityCreate(
            activity_code="ACT-1",
            name="Test",
            variance_percent=15.5,  # Phase 8 field
        )


def test_18_phase9_risk_fields_rejected():
    """Verify Phase 9 risk fields are rejected by schemas."""
    with pytest.raises(ValidationError):
        ScheduleActivityCreate(
            activity_code="ACT-1",
            name="Test",
            critical_path=True,  # Phase 9 field
        )


def test_19_match_list_remains_strongly_typed():
    """Verify MatchRecommendationListResponse enforces strongly typed items."""
    now = datetime.now(timezone.utc)
    match_rec = MatchRecommendationResponse(
        id=uuid4(),
        project_id=uuid4(),
        extraction_id=uuid4(),
        recommended_activity_id=uuid4(),
        confidence_score=0.92,
        created_at=now,
        updated_at=now,
    )
    list_res = MatchRecommendationListResponse(items=[match_rec], total=1)
    assert len(list_res.items) == 1
    assert list_res.items[0].confidence_score == 0.92


def test_20_embedding_metadata_contract():
    """Verify ActivityEmbeddingMetadata fields and types."""
    act_id = uuid4()
    proj_id = uuid4()
    now = datetime.now(timezone.utc)
    meta = ActivityEmbeddingMetadata(
        schedule_activity_id=act_id,
        project_id=proj_id,
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        created_at=now,
        updated_at=now,
    )
    assert meta.schedule_activity_id == act_id
    assert meta.project_id == proj_id
    assert len(meta.content_hash) == 64


def test_21_no_vector_exposed_in_public_schemas():
    """Verify embedding vector floats are not present on public schedule response models."""
    response_fields = ScheduleActivityResponse.model_fields.keys()
    assert "embedding" not in response_fields
    assert "vector" not in response_fields

    match_fields = MatchRecommendationResponse.model_fields.keys()
    assert "embedding" not in match_fields
    assert "query_vector" not in match_fields


def test_22_serialization_deserialization_round_trip():
    """Verify complete JSON dump and load round trip preserves data integrity."""
    act_id = uuid4()
    proj_id = uuid4()
    ext_id = uuid4()
    now = datetime.now(timezone.utc)

    orig = MatchRecommendationResponse(
        id=uuid4(),
        project_id=proj_id,
        extraction_id=ext_id,
        activity_index=1,
        recommended_activity_id=act_id,
        recommended_activity_code="ACT-888",
        recommended_activity_name="Structural Steel Assembly",
        confidence_score=0.875,
        scoring_breakdown=ScoringBreakdown(
            semantic_similarity=0.85,
            discipline_contribution=0.90,
            location_contribution=0.80,
            temporal_contribution=1.0,
        ),
        alternative_matches=[
            AlternativeMatch(
                schedule_activity_id=uuid4(),
                activity_code="ACT-889",
                activity_name="Steel Decking Installation",
                confidence_score=0.74,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    json_str = orig.model_dump_json()
    loaded_dict = json.loads(json_str)
    reconstructed = MatchRecommendationResponse.model_validate(loaded_dict)

    assert reconstructed.id == orig.id
    assert reconstructed.activity_index == 1
    assert reconstructed.confidence_score == 0.875
    assert reconstructed.confidence_level == MatchConfidenceLevel.HIGH
    assert len(reconstructed.alternative_matches) == 1
    assert reconstructed.alternative_matches[0].activity_code == "ACT-889"
