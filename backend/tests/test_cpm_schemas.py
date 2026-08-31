"""
SiteSync AI — Phase 9.2 CPM Pydantic v2 Schema Tests.
Verifies data contracts, constraints, extra="forbid", and validation errors.
"""

from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.cpm import (
    CPMActivityInput,
    CPMActivityNode,
    CPMDependencyInput,
    CPMNetworkResult,
    DependencyRelationshipType,
)

PROJECT_ID = uuid4()


def test_1_valid_cpm_activity_input():
    """Verify construction of valid CPMActivityInput."""
    act = CPMActivityInput(
        activity_id=uuid4(),
        project_id=PROJECT_ID,
        activity_code="ACT-101",
        name="Foundation Concrete",
        wbs_code="1.1",
        discipline="Civil",
        location="Zone A",
        planned_start_date=date(2026, 8, 1),
        planned_finish_date=date(2026, 8, 10),
    )
    assert act.activity_code == "ACT-101"
    assert act.planned_start_date == date(2026, 8, 1)
    assert act.planned_finish_date == date(2026, 8, 10)


def test_2_invalid_date_ordering_rejected():
    """Verify planned_start_date > planned_finish_date raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        CPMActivityInput(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Invalid Dates",
            planned_start_date=date(2026, 8, 10),
            planned_finish_date=date(2026, 8, 5),
        )
    assert "planned_start_date" in str(exc_info.value)
    assert "must not be later than planned_finish_date" in str(exc_info.value)


def test_3_blank_activity_code_or_name_rejected():
    """Verify empty or whitespace-only code/name are rejected."""
    with pytest.raises(ValidationError):
        CPMActivityInput(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="   ",
            name="Valid Name",
        )
    with pytest.raises(ValidationError):
        CPMActivityInput(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="   ",
        )


def test_4_valid_cpm_dependency_input():
    """Verify construction of valid CPMDependencyInput."""
    p_id = uuid4()
    s_id = uuid4()
    dep = CPMDependencyInput(
        dependency_id=uuid4(),
        project_id=PROJECT_ID,
        predecessor_id=p_id,
        successor_id=s_id,
        relationship_type=DependencyRelationshipType.FS,
        lag_days=2,
    )
    assert dep.relationship_type == DependencyRelationshipType.FS
    assert dep.lag_days == 2


def test_5_self_dependency_rejected_by_schema():
    """Verify predecessor_id == successor_id raises ValidationError."""
    same_id = uuid4()
    with pytest.raises(ValidationError) as exc_info:
        CPMDependencyInput(
            dependency_id=uuid4(),
            project_id=PROJECT_ID,
            predecessor_id=same_id,
            successor_id=same_id,
        )
    assert "Self-dependency is forbidden" in str(exc_info.value)


def test_6_extra_fields_forbidden():
    """Verify extra='forbid' rejects client injection."""
    with pytest.raises(ValidationError):
        CPMActivityInput(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Test",
            injected_field="malicious",
        )
    with pytest.raises(ValidationError):
        CPMDependencyInput(
            dependency_id=uuid4(),
            project_id=PROJECT_ID,
            predecessor_id=uuid4(),
            successor_id=uuid4(),
            unauthorized="injected",
        )


def test_7_relationship_type_enum_validation():
    """Verify supported PDM relationship types: FS, SS, FF, SF."""
    assert DependencyRelationshipType.FS == "FS"
    assert DependencyRelationshipType.SS == "SS"
    assert DependencyRelationshipType.FF == "FF"
    assert DependencyRelationshipType.SF == "SF"

    with pytest.raises(ValidationError):
        CPMDependencyInput(
            dependency_id=uuid4(),
            project_id=PROJECT_ID,
            predecessor_id=uuid4(),
            successor_id=uuid4(),
            relationship_type="INVALID_TYPE",  # type: ignore
        )


def test_8_cpm_network_result_schema():
    """Verify structure of CPMNetworkResult model."""
    res = CPMNetworkResult(
        project_id=PROJECT_ID,
        project_start_date=date(2026, 8, 1),
        project_finish_date=date(2026, 8, 20),
        total_activities=2,
        critical_activities_count=1,
        nodes=[],
        critical_path=[],
    )
    assert res.total_activities == 2
    assert res.critical_activities_count == 1
