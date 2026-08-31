"""
SiteSync AI — Phase 9.2 Critical Path Method (CPM) Domain Schemas.
Implements authoritative Pydantic v2 data models for:
  - CPM activity and dependency inputs
  - Supported PDM relationship types (ADR-014)
  - CPM calculated nodes with Early/Late dates, Floats, and Criticality (ADR-015)
  - Full CPM network analysis result wrapper
Strictly enforces extra="forbid" to reject unauthorized downstream fields.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# Canonical Relationship Type Enum (ADR-014)
# ==============================================================================

class DependencyRelationshipType(str, Enum):
    """
    Precedence Diagramming Method (PDM) relationship types.
    """
    FS = "FS"  # Finish-to-Start (Standard default)
    SS = "SS"  # Start-to-Start
    FF = "FF"  # Finish-to-Finish
    SF = "SF"  # Start-to-Finish


# ==============================================================================
# Domain Input Models
# ==============================================================================

class CPMActivityInput(BaseModel):
    """
    Input model representing a schedule activity supplied to the CPM calculation engine.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(
        description="Unique identifier of the schedule activity",
    )
    project_id: UUID = Field(
        description="Project identifier for tenant verification",
    )
    activity_code: str = Field(
        description="Project-unique activity code (e.g. 'ACT-101')",
    )
    name: str = Field(
        description="Title or descriptive name of the activity",
    )
    wbs_code: str | None = Field(
        default=None,
        description="Work Breakdown Structure reference code",
    )
    discipline: str | None = Field(
        default=None,
        description="Trade discipline (e.g. 'Civil', 'Piping')",
    )
    location: str | None = Field(
        default=None,
        description="Physical site area or grid location",
    )
    planned_start_date: date | None = Field(
        default=None,
        description="Baseline planned start date",
    )
    planned_finish_date: date | None = Field(
        default=None,
        description="Baseline planned finish date",
    )

    @field_validator("activity_code", "name")
    @classmethod
    def validate_non_blank(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty or whitespace only")
        return v.strip()

    @model_validator(mode="after")
    def validate_date_ordering(self) -> CPMActivityInput:
        if self.planned_start_date is not None and self.planned_finish_date is not None:
            if self.planned_start_date > self.planned_finish_date:
                raise ValueError(
                    f"planned_start_date ({self.planned_start_date}) must not be later than "
                    f"planned_finish_date ({self.planned_finish_date})"
                )
        return self


class CPMDependencyInput(BaseModel):
    """
    Input model representing a directed dependency edge supplied to the CPM calculation engine.
    """
    model_config = ConfigDict(extra="forbid")

    dependency_id: UUID = Field(
        description="Unique identifier of the dependency edge",
    )
    project_id: UUID = Field(
        description="Project identifier for tenant verification",
    )
    predecessor_id: UUID = Field(
        description="Activity ID of the upstream predecessor",
    )
    successor_id: UUID = Field(
        description="Activity ID of the downstream successor",
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
    def validate_no_self_dependency(self) -> CPMDependencyInput:
        if self.predecessor_id == self.successor_id:
            raise ValueError(
                f"Self-dependency is forbidden: predecessor_id and successor_id are identical ({self.predecessor_id})"
            )
        return self


# ==============================================================================
# Domain Output Models (ADR-015)
# ==============================================================================

class CPMActivityNode(BaseModel):
    """
    Calculated CPM metrics for an individual schedule activity node.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(description="Unique activity ID")
    project_id: UUID = Field(description="Project ID")
    activity_code: str = Field(description="Activity code")
    name: str = Field(description="Activity title")
    wbs_code: str | None = Field(default=None, description="WBS code")
    discipline: str | None = Field(default=None, description="Discipline")
    location: str | None = Field(default=None, description="Location")
    planned_start_date: date | None = Field(default=None, description="Baseline start date")
    planned_finish_date: date | None = Field(default=None, description="Baseline finish date")
    duration_days: int = Field(description="Derived inclusive calendar duration in days")

    early_start: date | None = Field(default=None, description="Early Start date (ES)")
    early_finish: date | None = Field(default=None, description="Early Finish date (EF)")
    late_start: date | None = Field(default=None, description="Late Start date (LS)")
    late_finish: date | None = Field(default=None, description="Late Finish date (LF)")

    total_float: int | None = Field(default=None, description="Total Float (TF) in calendar days")
    free_float: int | None = Field(default=None, description="Free Float (FF) in calendar days")
    is_critical: bool = Field(default=False, description="True iff Total Float <= 0")


class CPMNetworkResult(BaseModel):
    """
    Comprehensive result of a full CPM forward/backward pass on a project schedule network.
    """
    model_config = ConfigDict(extra="forbid")

    project_id: UUID = Field(description="Project ID")
    project_start_date: date | None = Field(default=None, description="Project anchor start date")
    project_finish_date: date | None = Field(default=None, description="Project finish anchor date")
    total_activities: int = Field(ge=0, description="Total activities in network")
    critical_activities_count: int = Field(ge=0, description="Count of activities on critical path")
    nodes: list[CPMActivityNode] = Field(description="All calculated activity nodes in topological order")
    critical_path: list[UUID] = Field(
        description="Ordered list of activity IDs belonging to the critical path (TF <= 0)",
    )
