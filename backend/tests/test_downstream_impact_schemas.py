"""
SiteSync AI — Phase 9.3 Downstream Impact Pydantic v2 Schema Tests.
Verifies data contracts, constraints, extra="forbid", and validation errors.
"""

from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.cpm import DependencyRelationshipType
from app.schemas.downstream_impact import (
    DownstreamImpactResult,
    DownstreamImpactSeverity,
    ImpactedSuccessorNode,
)

PROJECT_ID = uuid4()


def test_1_valid_impacted_successor_node():
    """Verify construction of valid ImpactedSuccessorNode."""
    node = ImpactedSuccessorNode(
        activity_id=uuid4(),
        activity_code="ACT-102",
        name="Piping Installation",
        wbs_code="1.2",
        discipline="Piping",
        depth=1,
        path=["ACT-101", "ACT-102"],
        relationship_with_immediate_predecessor=DependencyRelationshipType.FS,
        lag_days_with_immediate_predecessor=0,
        planned_start_date=date(2026, 8, 11),
        planned_finish_date=date(2026, 8, 20),
        total_float=5,
        free_float=2,
        is_critical=False,
        is_completed=False,
        impact_severity=DownstreamImpactSeverity.BUFFER_ABSORBED,
        available_float=5,
        float_consumed=3,
        projected_delay_days=0,
    )
    assert node.activity_code == "ACT-102"
    assert node.depth == 1
    assert node.impact_severity == DownstreamImpactSeverity.BUFFER_ABSORBED
    assert node.float_consumed == 3
    assert node.projected_delay_days == 0


def test_2_extra_fields_forbidden():
    """Verify extra='forbid' rejects client injection."""
    with pytest.raises(ValidationError):
        ImpactedSuccessorNode(
            activity_id=uuid4(),
            activity_code="ACT-102",
            name="Piping",
            depth=1,
            path=["ACT-101", "ACT-102"],
            impact_severity=DownstreamImpactSeverity.BUFFER_ABSORBED,
            injected_field="malicious",
        )


def test_3_downstream_impact_result_schema():
    """Verify construction of DownstreamImpactResult."""
    source_id = uuid4()
    res = DownstreamImpactResult(
        project_id=PROJECT_ID,
        source_activity_id=source_id,
        source_activity_code="ACT-101",
        source_name="Foundation Concrete",
        source_delay_days=4,
        is_source_critical=True,
        total_downstream_activities_count=2,
        critical_slippage_count=1,
        buffer_absorbed_count=1,
        historical_completed_count=0,
        impacted_successors=[],
    )
    assert res.source_delay_days == 4
    assert res.critical_slippage_count == 1
    assert res.buffer_absorbed_count == 1
