"""
SiteSync AI — Phase 9.5 Schedule Dependency & Critical Path API Schemas.
Implements authoritative Pydantic v2 data models for:
  - Schedule dependency creation and responses
  - Schedule dependency list collections
  - Critical Path Method (CPM) calculated node responses
  - Critical Path analysis API response wrapper
Strictly enforces extra="forbid" to reject unauthorized downstream fields.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.cpm import DependencyRelationshipType


# ==============================================================================
# Dependency Request / Response Models
# ==============================================================================

class DependencyCreate(BaseModel):
    """
    Payload for creating a new directed schedule dependency edge.
    Note: project_id is strictly derived from URL path and forbidden in body.
    """
    model_config = ConfigDict(extra="forbid")

    predecessor_id: UUID = Field(
        ...,
        description="Activity ID of the upstream predecessor activity",
    )
    successor_id: UUID = Field(
        ...,
        description="Activity ID of the downstream successor activity",
    )
    relationship_type: DependencyRelationshipType = Field(
        default=DependencyRelationshipType.FS,
        description="PDM relationship type (FS, SS, FF, SF)",
    )
    lag_days: int = Field(
        default=0,
        description="Lag in calendar days (negative indicates lead time)",
    )

    @model_validator(mode="after")
    def validate_no_self_dependency(self) -> DependencyCreate:
        if self.predecessor_id == self.successor_id:
            raise ValueError(
                f"Self-dependency is forbidden: predecessor_id and successor_id are identical ({self.predecessor_id})"
            )
        return self


class DependencyResponse(BaseModel):
    """
    Response model representing a persisted schedule dependency relationship.
    """
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(description="Unique dependency relationship ID")
    project_id: UUID = Field(description="Project tenant identifier")
    predecessor_id: UUID = Field(description="Upstream predecessor activity ID")
    successor_id: UUID = Field(description="Downstream successor activity ID")
    relationship_type: DependencyRelationshipType = Field(description="PDM relationship type")
    lag_days: int = Field(description="Lag in calendar days")
    created_at: datetime = Field(description="Timestamp when edge was created")
    updated_at: datetime = Field(description="Timestamp when edge was last updated")


class DependencyListResponse(BaseModel):
    """
    Collection wrapper for schedule dependencies scoped to a project.
    """
    model_config = ConfigDict(extra="forbid")

    items: list[DependencyResponse] = Field(description="List of dependency edges in deterministic order")
    total: int = Field(ge=0, description="Total count of dependencies")


# ==============================================================================
# Critical Path Method (CPM) Response Models
# ==============================================================================

class CPMActivityNodeResponse(BaseModel):
    """
    Calculated CPM metrics for an individual activity node in API responses.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(description="Unique activity ID")
    project_id: UUID = Field(description="Project ID")
    activity_code: str = Field(description="Activity code")
    name: str = Field(description="Activity title")
    wbs_code: Optional[str] = Field(default=None, description="WBS code")
    discipline: Optional[str] = Field(default=None, description="Trade discipline")
    location: Optional[str] = Field(default=None, description="Physical site area")
    planned_start_date: Optional[date] = Field(default=None, description="Baseline start date")
    planned_finish_date: Optional[date] = Field(default=None, description="Baseline finish date")
    duration_days: int = Field(description="Derived inclusive calendar duration in days")

    early_start: Optional[date] = Field(default=None, description="Early Start date (ES)")
    early_finish: Optional[date] = Field(default=None, description="Early Finish date (EF)")
    late_start: Optional[date] = Field(default=None, description="Late Start date (LS)")
    late_finish: Optional[date] = Field(default=None, description="Late Finish date (LF)")

    total_float_days: Optional[int] = Field(default=None, description="Total Float in calendar days")
    free_float_days: Optional[int] = Field(default=None, description="Free Float in calendar days")
    is_critical: bool = Field(default=False, description="True iff Total Float <= 0")


class CriticalPathResponse(BaseModel):
    """
    Response model for Critical Path Method (CPM) network analysis endpoint.
    """
    model_config = ConfigDict(extra="forbid")

    project_id: UUID = Field(description="Project tenant ID")
    project_start_date: Optional[date] = Field(default=None, description="Project start anchor date")
    project_finish_date: Optional[date] = Field(default=None, description="Project finish anchor date")
    total_activities: int = Field(ge=0, description="Total activities in network")
    critical_activities_count: int = Field(ge=0, description="Count of activities on critical path")
    critical_path_activity_ids: list[UUID] = Field(
        description="Ordered list of activity IDs on the critical path",
    )
    activities: list[CPMActivityNodeResponse] = Field(
        description="All calculated activity nodes in deterministic topological order",
    )
