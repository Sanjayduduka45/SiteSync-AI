"""
SiteSync AI — Phase 9.4 Risk Intelligence Pydantic v2 Schema Tests.
Verifies data contracts, constraints, extra="forbid", and validation errors.
"""

from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.risk import (
    ActivityRiskAssessment,
    ProjectRiskSummary,
    RiskCategory,
    RiskSeverityLevel,
)
from app.schemas.variance import ActivityVarianceStatus

PROJECT_ID = uuid4()


def test_1_valid_activity_risk_assessment_schema():
    """Verify construction of valid ActivityRiskAssessment."""
    assessment = ActivityRiskAssessment(
        activity_id=uuid4(),
        project_id=PROJECT_ID,
        activity_code="ACT-101",
        name="Foundation Concrete",
        wbs_code="1.1",
        discipline="Civil",
        location="Zone A",
        severity=RiskSeverityLevel.CRITICAL,
        risk_score=90,
        categories=[RiskCategory.CRITICAL_PATH_DELAY, RiskCategory.DOWNSTREAM_BOTTLENECK],
        is_critical_path=True,
        total_float=0,
        date_variance_days=3,
        direct_successors_count=4,
        transitive_successors_count=6,
        critical_slippage_successors_count=3,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
        progress_percent=45.0,
        is_completed=False,
    )
    assert assessment.severity == RiskSeverityLevel.CRITICAL
    assert assessment.risk_score == 90
    assert len(assessment.categories) == 2


def test_2_extra_fields_forbidden():
    """Verify extra='forbid' rejects client injection."""
    with pytest.raises(ValidationError):
        ActivityRiskAssessment(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Foundation",
            severity=RiskSeverityLevel.LOW,
            risk_score=15,
            injected_field="malicious",
        )


def test_3_risk_score_bounds_validation():
    """Verify risk_score is bounded in [0, 100]."""
    with pytest.raises(ValidationError):
        ActivityRiskAssessment(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Test",
            severity=RiskSeverityLevel.LOW,
            risk_score=-5,
        )
    with pytest.raises(ValidationError):
        ActivityRiskAssessment(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Test",
            severity=RiskSeverityLevel.CRITICAL,
            risk_score=105,
        )


def test_4_project_risk_summary_schema():
    """Verify ProjectRiskSummary structure and aggregation fields."""
    summary = ProjectRiskSummary(
        project_id=PROJECT_ID,
        total_activities=10,
        critical_severity_count=2,
        high_severity_count=3,
        medium_severity_count=4,
        low_severity_count=1,
        critical_path_delay_count=2,
        float_erosion_count=2,
        downstream_bottleneck_count=1,
        predecessor_blocker_count=1,
        unquantified_milestone_lag_count=0,
        unit_mismatch_exposure_count=0,
        average_risk_score=54.2,
        items=[],
    )
    assert summary.total_activities == 10
    assert summary.critical_severity_count == 2
    assert summary.average_risk_score == 54.2
