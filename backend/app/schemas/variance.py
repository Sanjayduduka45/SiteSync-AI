"""
SiteSync AI — Phase 8.1 Plan vs Actual Variance Domain Schemas.
Implements authoritative Pydantic v2 data models for:
  - Activity variance inputs and results
  - Canonical activity status lifecycle (ADR-011)
  - Homogeneous-unit WBS and Project rollups (ADR-012)
  - Strict security boundaries (extra="forbid", zero Phase 9 concepts)
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Canonical Variance Enums (ADR-011)
# ==============================================================================

class ActivityVarianceStatus(str, Enum):
    """
    Canonical physical progress and schedule alignment status for an activity.
    Strictly deterministic based on valid quantities, unit compatibility, and scope.
    """
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVER_DELIVERED = "over_delivered"
    UNQUANTIFIED = "unquantified"
    UNIT_MISMATCH = "unit_mismatch"


# ==============================================================================
# Activity Variance Inputs
# ==============================================================================

class ApprovedActualInput(BaseModel):
    """
    Input model representing a human-approved actual progress record
    from public.approved_actuals needed for variance calculation.
    """
    model_config = ConfigDict(extra="forbid")

    actual_quantity: float | None = Field(
        default=None,
        description="Human-verified physical work quantity (must be >= 0 if provided)",
    )
    actual_unit: str | None = Field(
        default=None,
        description="Unit of measure for the reported actual progress",
    )
    actual_date: date = Field(
        description="Verified date when physical work was executed on site",
    )

    @field_validator("actual_quantity")
    @classmethod
    def validate_non_negative_actual(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("actual_quantity must be greater than or equal to 0")
        return v

    @field_validator("actual_unit")
    @classmethod
    def normalize_unit_str(cls, v: str | None) -> str | None:
        if v is not None:
            v_trimmed = v.strip()
            return v_trimmed if v_trimmed else None
        return None


class ActivityVarianceInput(BaseModel):
    """
    Input model containing baseline schedule activity details alongside
    all approved actual records assigned to that activity.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(description="Unique identifier of schedule activity")
    project_id: UUID = Field(description="Project tenant identifier")
    activity_code: str = Field(description="Activity code (e.g. ACT-1001)")
    name: str = Field(description="Activity title / description")
    wbs_code: str | None = Field(default=None, description="Work Breakdown Structure tier code")
    discipline: str | None = Field(default=None, description="Trade discipline")
    location: str | None = Field(default=None, description="Physical location / area")

    planned_quantity: float | None = Field(
        default=None,
        description="Baseline planned work quantity (must be >= 0 if provided, NULL for unquantified/milestone)",
    )
    planned_unit: str | None = Field(
        default=None,
        description="Baseline planned unit of measure",
    )
    planned_start_date: date | None = Field(
        default=None,
        description="Baseline planned start date",
    )
    planned_finish_date: date | None = Field(
        default=None,
        description="Baseline planned finish date",
    )

    approved_actuals: list[ApprovedActualInput] = Field(
        default_factory=list,
        description="List of all approved actual progress records for this activity",
    )

    @field_validator("planned_quantity")
    @classmethod
    def validate_non_negative_planned(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("planned_quantity must be greater than or equal to 0")
        return v

    @field_validator("activity_code", "name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        v_trimmed = v.strip()
        if not v_trimmed:
            raise ValueError("String field cannot be empty or whitespace only")
        return v_trimmed

    @field_validator("planned_unit", "wbs_code", "discipline", "location")
    @classmethod
    def normalize_optional_strings(cls, v: str | None) -> str | None:
        if v is not None:
            v_trimmed = v.strip()
            return v_trimmed if v_trimmed else None
        return None


# ==============================================================================
# Activity Variance Response (ADR-009, ADR-011)
# ==============================================================================

class ActivityVarianceItem(BaseModel):
    """
    Deterministic plan vs actual variance result for a single schedule activity.
    """
    model_config = ConfigDict(extra="forbid")

    # Identity
    activity_id: UUID
    project_id: UUID
    activity_code: str
    name: str
    wbs_code: str | None = None
    discipline: str | None = None
    location: str | None = None

    # Baseline Plan
    planned_quantity: float | None = None
    planned_unit: str | None = None
    planned_start_date: date | None = None
    planned_finish_date: date | None = None

    # Human-Verified Actual
    actual_quantity_total: float | None = None
    actual_unit: str | None = None
    latest_actual_date: date | None = None
    approved_actuals_count: int = 0

    # Calculated Metrics (ADR-009)
    quantity_variance: float | None = None
    progress_percent: float | None = None
    date_variance_days: int | None = None

    # Status & Flags (ADR-011, ADR-013)
    variance_status: ActivityVarianceStatus
    is_flagged: bool = False
    flag_reason: str | None = None


# ==============================================================================
# Rollup Models (ADR-012)
# ==============================================================================

class UnitRollup(BaseModel):
    """
    Homogeneous-unit physical quantity aggregate.
    Prevents meaningless cross-unit additions or unweighted percentage averages.
    """
    model_config = ConfigDict(extra="forbid")

    unit: str
    planned_total: float
    actual_total: float
    quantity_variance: float
    progress_percent: float | None = None
    activity_count: int = 0


class WbsRollup(BaseModel):
    """
    WBS-tier rollup grouping compatible unit rollups and activity counts.
    """
    model_config = ConfigDict(extra="forbid")

    wbs_code: str
    unit_rollups: list[UnitRollup] = Field(default_factory=list)
    unquantified_activity_count: int = 0
    unit_mismatch_activity_count: int = 0
    total_activity_count: int = 0


class ProjectVarianceSummary(BaseModel):
    """
    High-level project plan vs actual variance summary.
    """
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    total_activities: int
    activities_with_progress: int
    completed_activities: int
    in_progress_activities: int
    not_started_activities: int
    over_delivered_activities: int
    unquantified_activities: int
    unit_mismatch_activities: int
    flagged_variance_count: int = 0
    overall_progress_percent: float | None = None
    unit_rollups: list[UnitRollup] = Field(default_factory=list)


class ActivityVarianceListResponse(BaseModel):
    """
    Paginated list response for activity variance items.
    """
    model_config = ConfigDict(extra="forbid")

    items: list[ActivityVarianceItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class WbsVarianceListResponse(BaseModel):
    """
    List response for WBS rollup items.
    """
    model_config = ConfigDict(extra="forbid")

    items: list[WbsRollup] = Field(default_factory=list)
    total: int = 0

