"""
SiteSync AI — Phase 8.1 Variance Schemas Unit Tests.
Verifies strict validation, extra-field forbidding, non-negative constraints,
and exclusion of Phase 9 concepts on Pydantic v2 variance models.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.variance import (
    ActivityVarianceInput,
    ActivityVarianceItem,
    ActivityVarianceStatus,
    ApprovedActualInput,
    ProjectVarianceSummary,
    UnitRollup,
    WbsRollup,
)


def test_1_valid_approved_actual_input():
    """Verify valid ApprovedActualInput creation."""
    actual = ApprovedActualInput(
        actual_quantity=15.5,
        actual_unit="  LF  ",
        actual_date=date(2026, 8, 30),
    )
    assert actual.actual_quantity == 15.5
    assert actual.actual_unit == "LF"
    assert actual.actual_date == date(2026, 8, 30)


def test_2_negative_actual_quantity_rejected():
    """Verify negative actual quantity raises validation error."""
    with pytest.raises(ValidationError) as exc:
        ApprovedActualInput(
            actual_quantity=-1.0,
            actual_unit="tons",
            actual_date=date(2026, 8, 30),
        )
    assert "actual_quantity must be greater than or equal to 0" in str(exc.value)


def test_3_valid_activity_variance_input():
    """Verify valid ActivityVarianceInput creation with nested actuals."""
    act_id = uuid4()
    proj_id = uuid4()
    item = ActivityVarianceInput(
        activity_id=act_id,
        project_id=proj_id,
        activity_code="ACT-101",
        name="Structural Steel Framing",
        wbs_code="1.2.1",
        discipline="Civil",
        location="Grid 4",
        planned_quantity=100.0,
        planned_unit="tons",
        planned_start_date=date(2026, 8, 1),
        planned_finish_date=date(2026, 8, 30),
        approved_actuals=[
            ApprovedActualInput(
                actual_quantity=25.0,
                actual_unit="tons",
                actual_date=date(2026, 8, 10),
            ),
            ApprovedActualInput(
                actual_quantity=35.0,
                actual_unit="tons",
                actual_date=date(2026, 8, 20),
            ),
        ],
    )
    assert item.activity_id == act_id
    assert item.planned_quantity == 100.0
    assert len(item.approved_actuals) == 2


def test_4_negative_planned_quantity_rejected():
    """Verify negative planned quantity raises validation error."""
    with pytest.raises(ValidationError) as exc:
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="Structural Steel Framing",
            planned_quantity=-50.0,
        )
    assert "planned_quantity must be greater than or equal to 0" in str(exc.value)


def test_5_blank_activity_code_or_name_rejected():
    """Verify blank or whitespace-only code/name strings are rejected."""
    with pytest.raises(ValidationError):
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="   ",
            name="Valid Name",
        )

    with pytest.raises(ValidationError):
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="",
        )


def test_6_extra_fields_forbidden():
    """Verify extra fields are strictly rejected across all models."""
    with pytest.raises(ValidationError):
        ApprovedActualInput(
            actual_quantity=10.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 30),
            extra_field="malicious",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="Test",
            approved_by=str(uuid4()),  # type: ignore[call-arg]
        )


def test_7_client_identity_injection_rejected():
    """Verify identity injection fields are rejected by schemas."""
    with pytest.raises(ValidationError):
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="Test",
            planner_id=str(uuid4()),  # type: ignore[call-arg]
            jwt="token",  # type: ignore[call-arg]
        )


def test_8_phase9_fields_rejected_by_schema():
    """Verify Phase 9 fields cannot be passed to Phase 8 schemas."""
    with pytest.raises(ValidationError):
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="Test",
            variance_status=ActivityVarianceStatus.IN_PROGRESS,
            critical_path=True,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-101",
            name="Test",
            variance_status=ActivityVarianceStatus.IN_PROGRESS,
            risk_score=85,  # type: ignore[call-arg]
        )


def test_9_rollup_models_validation():
    """Verify UnitRollup, WbsRollup, and ProjectVarianceSummary models."""
    proj_id = uuid4()
    unit_rollup = UnitRollup(
        unit="LF",
        planned_total=500.0,
        actual_total=250.0,
        quantity_variance=-250.0,
        progress_percent=50.0,
        activity_count=3,
    )
    assert unit_rollup.quantity_variance == -250.0
    assert unit_rollup.progress_percent == 50.0

    wbs = WbsRollup(
        wbs_code="1.2",
        unit_rollups=[unit_rollup],
        unquantified_activity_count=1,
        unit_mismatch_activity_count=0,
        total_activity_count=4,
    )
    assert wbs.wbs_code == "1.2"
    assert wbs.total_activity_count == 4

    summary = ProjectVarianceSummary(
        project_id=proj_id,
        total_activities=10,
        activities_with_progress=4,
        completed_activities=2,
        in_progress_activities=2,
        not_started_activities=5,
        over_delivered_activities=0,
        unquantified_activities=1,
        unit_mismatch_activities=0,
        flagged_variance_count=0,
        unit_rollups=[unit_rollup],
    )
    assert summary.total_activities == 10
    assert summary.completed_activities == 2
