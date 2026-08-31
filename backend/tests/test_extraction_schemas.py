"""
Tests for Pydantic v2 AI Extraction Schemas — SiteSync AI Phase 5.
Validates structural integrity, field constraints, UUID parsing, and confidence scoring rules.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from app.schemas.extractions import (
    ConfidenceLevel,
    ExtractedActivity,
    ExtractionResult,
    ExtractionStatus,
)


def test_valid_extracted_activity_creation():
    act = ExtractedActivity(
        description="Erected pipe spool 102 on Rack 3",
        progress_value=75.0,
        progress_unit="%",
        discipline="Piping",
        location="Unit 1, Area B",
        event_date=date(2026, 8, 30),
        constraints=["Crane delay of 2 hours"],
        evidence_tokens=["spool 102", "Rack 3", "75%"],
    )
    assert act.description == "Erected pipe spool 102 on Rack 3"
    assert act.progress_value == 75.0
    assert act.progress_unit == "%"
    assert act.discipline == "Piping"
    assert act.location == "Unit 1, Area B"
    assert act.event_date == date(2026, 8, 30)
    assert act.constraints == ["Crane delay of 2 hours"]
    assert act.evidence_tokens == ["spool 102", "Rack 3", "75%"]


def test_extracted_activity_defaults():
    act = ExtractedActivity(description="Welding inspection complete")
    assert act.description == "Welding inspection complete"
    assert act.progress_value is None
    assert act.progress_unit is None
    assert act.discipline is None
    assert act.location is None
    assert act.event_date is None
    assert act.constraints == []
    assert act.evidence_tokens == []


def test_blank_activity_description_rejected():
    with pytest.raises(ValidationError) as exc:
        ExtractedActivity(description="   ")
    assert "Activity description cannot be empty" in str(exc.value)


def test_empty_string_activity_description_rejected():
    with pytest.raises(ValidationError):
        ExtractedActivity(description="")


def test_valid_extraction_result_creation():
    input_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    result = ExtractionResult(
        raw_input_id=input_id,
        extracted_activities=[
            ExtractedActivity(description="Poured 25 m3 concrete for foundation"),
        ],
        extraction_confidence=0.92,
        model_version="gemini-1.5-flash:v1",
        processing_timestamp=now,
    )
    assert result.raw_input_id == input_id
    assert len(result.extracted_activities) == 1
    assert result.extraction_confidence == 0.92
    assert result.confidence_level == ConfidenceLevel.HIGH
    assert result.model_version == "gemini-1.5-flash:v1"
    assert result.processing_timestamp == now


def test_invalid_uuid_rejected():
    with pytest.raises(ValidationError):
        ExtractionResult(
            raw_input_id="not-a-valid-uuid",  # type: ignore[arg-type]
            extraction_confidence=0.8,
            model_version="v1",
        )


def test_confidence_below_zero_rejected():
    with pytest.raises(ValidationError):
        ExtractionResult(
            raw_input_id=uuid.uuid4(),
            extraction_confidence=-0.05,
            model_version="v1",
        )


def test_confidence_above_one_rejected():
    with pytest.raises(ValidationError):
        ExtractionResult(
            raw_input_id=uuid.uuid4(),
            extraction_confidence=1.05,
            model_version="v1",
        )


def test_blank_model_version_rejected():
    with pytest.raises(ValidationError) as exc:
        ExtractionResult(
            raw_input_id=uuid.uuid4(),
            extraction_confidence=0.85,
            model_version="   ",
        )
    assert "Model version cannot be empty" in str(exc.value)


def test_confidence_classification_levels():
    input_id = uuid.uuid4()

    res_high = ExtractionResult(
        raw_input_id=input_id,
        extraction_confidence=0.85,
        model_version="v1",
    )
    assert res_high.confidence_level == ConfidenceLevel.HIGH

    res_med = ExtractionResult(
        raw_input_id=input_id,
        extraction_confidence=0.74,
        model_version="v1",
    )
    assert res_med.confidence_level == ConfidenceLevel.MEDIUM

    res_low = ExtractionResult(
        raw_input_id=input_id,
        extraction_confidence=0.45,
        model_version="v1",
    )
    assert res_low.confidence_level == ConfidenceLevel.LOW


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        ExtractedActivity(
            description="Test work",
            unsupported_field="arbitrary",  # type: ignore[call-arg]
        )


def test_immutability():
    act = ExtractedActivity(description="Test work")
    with pytest.raises(ValidationError):
        act.description = "Modified work"  # type: ignore[misc]
