"""
SiteSync AI — Phase 9.4 Risk Intelligence & Severity Domain Schemas.
Implements authoritative Pydantic v2 data models for:
  - Canonical 6-category risk taxonomy (ADR-017)
  - 4-level discrete severity classification (ADR-017)
  - Activity risk assessment with transparent composite scoring [0-100]
  - Project risk summary aggregation
Strictly enforces extra="forbid" to reject unauthorized client-supplied fields.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.variance import ActivityVarianceStatus


# ==============================================================================
# Canonical Risk Enums (ADR-017)
# ==============================================================================

class RiskSeverityLevel(str, Enum):
    """
    Discrete severity classification level.
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskCategory(str, Enum):
    """
    Canonical 6-category risk taxonomy for construction schedule intelligence.
    """
    CRITICAL_PATH_DELAY = "critical_path_delay"
    FLOAT_EROSION = "float_erosion"
    DOWNSTREAM_BOTTLENECK = "downstream_bottleneck"
    PREDECESSOR_BLOCKER = "predecessor_blocker"
    UNQUANTIFIED_MILESTONE_LAG = "unquantified_milestone_lag"
    UNIT_MISMATCH_EXPOSURE = "unit_mismatch_exposure"


# ==============================================================================
# Domain Risk Models
# ==============================================================================

class ActivityRiskAssessment(BaseModel):
    """
    Calculated deterministic risk intelligence for an individual schedule activity.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(description="Unique activity ID")
    project_id: UUID = Field(description="Project tenant ID")
    activity_code: str = Field(description="Activity code (e.g. 'ACT-101')")
    name: str = Field(description="Activity title")
    wbs_code: str | None = Field(default=None, description="WBS code")
    discipline: str | None = Field(default=None, description="Trade discipline")
    location: str | None = Field(default=None, description="Site location")

    severity: RiskSeverityLevel = Field(description="Discrete risk severity classification")
    risk_score: int = Field(ge=0, le=100, description="Deterministic composite score [0-100]")
    categories: list[RiskCategory] = Field(
        default_factory=list,
        description="List of active canonical risk categories applicable to this activity",
    )

    is_critical_path: bool = Field(default=False, description="True if activity is on baseline critical path (TF <= 0)")
    total_float: int | None = Field(default=None, description="Total Float in calendar days")
    date_variance_days: int | None = Field(default=None, description="Factual schedule date variance in days")
    direct_successors_count: int = Field(ge=0, default=0, description="Count of immediate direct successors")
    transitive_successors_count: int = Field(ge=0, default=0, description="Count of reachable downstream successors")
    critical_slippage_successors_count: int = Field(
        ge=0,
        default=0,
        description="Count of successors forced into critical delay",
    )

    variance_status: ActivityVarianceStatus | None = Field(
        default=None,
        description="Phase 8 verified activity status",
    )
    progress_percent: float | None = Field(
        default=None,
        description="Phase 8 verified progress percentage",
    )
    is_completed: bool = Field(default=False, description="True if activity is verified COMPLETED")


class ProjectRiskSummary(BaseModel):
    """
    Aggregated project-level risk summary and severity distribution.
    """
    model_config = ConfigDict(extra="forbid")

    project_id: UUID = Field(description="Project tenant ID")
    total_activities: int = Field(ge=0, description="Total assessed activities")
    critical_severity_count: int = Field(ge=0, description="Count of CRITICAL severity activities")
    high_severity_count: int = Field(ge=0, description="Count of HIGH severity activities")
    medium_severity_count: int = Field(ge=0, description="Count of MEDIUM severity activities")
    low_severity_count: int = Field(ge=0, description="Count of LOW severity activities")

    critical_path_delay_count: int = Field(ge=0, description="Activities with CRITICAL_PATH_DELAY")
    float_erosion_count: int = Field(ge=0, description="Activities with FLOAT_EROSION")
    downstream_bottleneck_count: int = Field(ge=0, description="Activities with DOWNSTREAM_BOTTLENECK")
    predecessor_blocker_count: int = Field(ge=0, description="Activities with PREDECESSOR_BLOCKER")
    unquantified_milestone_lag_count: int = Field(ge=0, description="Activities with UNQUANTIFIED_MILESTONE_LAG")
    unit_mismatch_exposure_count: int = Field(ge=0, description="Activities with UNIT_MISMATCH_EXPOSURE")

    average_risk_score: float | None = Field(
        default=None,
        description="Average risk score across all active activities",
    )
    items: list[ActivityRiskAssessment] = Field(
        description="List of assessed activities in deterministic sorted order",
    )


class ActivityRiskListResponse(BaseModel):
    """
    Paginated collection response for activity risk assessments.
    """
    model_config = ConfigDict(extra="forbid")

    items: list[ActivityRiskAssessment] = Field(description="List of assessed activities in deterministic order")
    total: int = Field(ge=0, description="Total matching items count")
    limit: int = Field(ge=1, description="Page limit")
    offset: int = Field(ge=0, description="Page offset")

