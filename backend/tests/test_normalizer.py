"""
Tests for Normalization Layer — SiteSync AI Phase 5.
Validates deterministic unit normalization, trade discipline standardization, and evidence token preservation.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import uuid

from app.ai.normalizer import (
    normalize_activity,
    normalize_discipline,
    normalize_extraction,
    normalize_unit,
)
from app.schemas.extractions import ExtractedActivity, ExtractionResult


def test_unit_normalization_length():
    assert normalize_unit("meters") == "m"
    assert normalize_unit("meter") == "m"
    assert normalize_unit("metre") == "m"
    assert normalize_unit("metres") == "m"
    assert normalize_unit("m") == "m"
    assert normalize_unit("feet") == "LF"
    assert normalize_unit("foot") == "LF"
    assert normalize_unit("ft") == "LF"
    assert normalize_unit("linear feet") == "LF"
    assert normalize_unit("LF") == "LF"


def test_unit_normalization_volume():
    assert normalize_unit("cubic meters") == "m3"
    assert normalize_unit("cubic meter") == "m3"
    assert normalize_unit("m3") == "m3"
    assert normalize_unit("m³") == "m3"
    assert normalize_unit("cubic yards") == "CY"
    assert normalize_unit("cubic yard") == "CY"
    assert normalize_unit("yd3") == "CY"
    assert normalize_unit("CY") == "CY"


def test_unit_normalization_percentage():
    assert normalize_unit("percent") == "%"
    assert normalize_unit("percentage") == "%"
    assert normalize_unit("%") == "%"


def test_unit_normalization_counts_and_weight():
    assert normalize_unit("spools") == "spools"
    assert normalize_unit("spool") == "spools"
    assert normalize_unit("tons") == "tons"
    assert normalize_unit("ton") == "tons"
    assert normalize_unit("tonne") == "tons"
    assert normalize_unit("joints") == "joints"
    assert normalize_unit("each") == "ea"
    assert normalize_unit("pieces") == "ea"


def test_unknown_unit_preserved():
    assert normalize_unit("banana-units") == "banana-units"
    assert normalize_unit("custom_barrel") == "custom_barrel"
    assert normalize_unit("unknown-metric") != "LF"


def test_none_and_empty_unit_safe():
    assert normalize_unit(None) is None
    assert normalize_unit("") is None
    assert normalize_unit("   ") is None


def test_discipline_normalization_standard_trades():
    assert normalize_discipline("piping") == "Piping"
    assert normalize_discipline("pipe") == "Piping"
    assert normalize_discipline("piping works") == "Piping"
    assert normalize_discipline("civil") == "Civil"
    assert normalize_discipline("civil works") == "Civil"
    assert normalize_discipline("concrete") == "Civil"
    assert normalize_discipline("electrical") == "Electrical"
    assert normalize_discipline("e&i") == "Electrical"
    assert normalize_discipline("structural") == "Structural"
    assert normalize_discipline("steel") == "Structural"
    assert normalize_discipline("mechanical") == "Mechanical"
    assert normalize_discipline("instrumentation") == "Instrumentation"
    assert normalize_discipline("scaffolding") == "Scaffolding"
    assert normalize_discipline("painting") == "Painting/Insulation"


def test_unknown_discipline_preserved():
    assert normalize_discipline("Geotechnical Drilling") == "Geotechnical Drilling"
    assert normalize_discipline("Underwater Diving") == "Underwater Diving"


def test_none_and_empty_discipline_safe():
    assert normalize_discipline(None) is None
    assert normalize_discipline("") is None
    assert normalize_discipline("   ") is None


def test_activity_normalization_preserves_description_and_evidence():
    raw_act = ExtractedActivity(
        description="Poured foundation pad T-101 using concrete pump",
        progress_value=45.5,
        progress_unit="cubic meters",
        discipline="civil works",
        location="Pad T-101",
        event_date=date(2026, 8, 30),
        constraints=["High wind warning"],
        evidence_tokens=["poured foundation pad", "45.5 cubic meters"],
    )

    norm_act = normalize_activity(raw_act)

    assert norm_act.description == "Poured foundation pad T-101 using concrete pump"
    assert norm_act.progress_value == 45.5
    assert norm_act.progress_unit == "m3"
    assert norm_act.discipline == "Civil"
    assert norm_act.location == "Pad T-101"
    assert norm_act.event_date == date(2026, 8, 30)
    assert norm_act.constraints == ["High wind warning"]
    assert norm_act.evidence_tokens == ["poured foundation pad", "45.5 cubic meters"]


def test_extraction_normalization_preserves_metadata():
    input_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    raw_result = ExtractionResult(
        raw_input_id=input_id,
        extracted_activities=[
            ExtractedActivity(
                description="Installed 12 spools of carbon steel piping",
                progress_value=12.0,
                progress_unit="spool",
                discipline="pipework",
                evidence_tokens=["12 spools"],
            ),
            ExtractedActivity(
                description="Pulled 350 meters of instrument cable",
                progress_value=350.0,
                progress_unit="meters",
                discipline="electrical works",
                evidence_tokens=["350 meters", "instrument cable"],
            ),
        ],
        extraction_confidence=0.88,
        model_version="gemini-1.5-flash:v1",
        processing_timestamp=now,
    )

    norm_result = normalize_extraction(raw_result)

    assert norm_result.raw_input_id == input_id
    assert norm_result.extraction_confidence == 0.88
    assert norm_result.model_version == "gemini-1.5-flash:v1"
    assert norm_result.processing_timestamp == now
    assert len(norm_result.extracted_activities) == 2

    # Activity 1
    assert norm_result.extracted_activities[0].progress_unit == "spools"
    assert norm_result.extracted_activities[0].discipline == "Piping"
    assert norm_result.extracted_activities[0].evidence_tokens == ["12 spools"]

    # Activity 2
    assert norm_result.extracted_activities[1].progress_unit == "m"
    assert norm_result.extracted_activities[1].discipline == "Electrical"
    assert norm_result.extracted_activities[1].evidence_tokens == ["350 meters", "instrument cable"]
