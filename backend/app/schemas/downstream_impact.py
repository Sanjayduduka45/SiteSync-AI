"""
SiteSync AI — Phase 9.3 Downstream Impact & Float Erosion Domain Schemas.
Implements authoritative Pydantic v2 data models for:
  - Downstream impact severity classification (ADR-016)
  - Impacted successor nodes in the transitive dependency DAG
  - Full downstream impact evaluation result wrapper
Strictly enforces extra="forbid" to reject unauthorized downstream fields.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cpm import DependencyRelationshipType


# ==============================================================================
# Canonical Impact Severity Enum (ADR-016)
# ==============================================================================

class DownstreamImpactSeverity(str, Enum):
    """
    Classification of downstream schedule consequence on a successor activity.
    """
    CRITICAL_SLIPPAGE = "critical_slippage"  # Upstream delay exceeds successor float buffer
    BUFFER_ABSORBED = "buffer_absorbed"      # Upstream delay absorbed by successor float buffer
    HISTORICAL_COMPLETED = "historical_completed"  # Successor is already completed on site
    UNAFFECTED = "unaffected"                # Source activity is on time or early (delay <= 0)


# ==============================================================================
# Impacted Successor Node Model
# ==============================================================================

class ImpactedSuccessorNode(BaseModel):
    """
    Detailed impact analysis for a single reachable downstream successor activity.
    """
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID = Field(description="Unique identifier of the successor activity")
    activity_code: str = Field(description="Activity code (e.g. 'ACT-102')")
    name: str = Field(description="Descriptive activity title")
    wbs_code: str | None = Field(default=None, description="WBS reference code")
    discipline: str | None = Field(default=None, description="Trade discipline")
    depth: int = Field(ge=1, description="Shortest hop distance from the source delayed activity")
    path: list[str] = Field(description="Activity codes along the primary traversal path from source")

    relationship_with_immediate_predecessor: DependencyRelationshipType | None = Field(
        default=None,
        description="PDM relationship type with the direct predecessor on traversal path",
    )
    lag_days_with_immediate_predecessor: int = Field(
        default=0,
        description="Lag days on the direct predecessor relationship",
    )

    planned_start_date: date | None = Field(default=None, description="Baseline start date")
    planned_finish_date: date | None = Field(default=None, description="Baseline finish date")
    total_float: int | None = Field(default=None, description="Total Float (TF) in calendar days")
    free_float: int | None = Field(default=None, description="Free Float (FF) in calendar days")
    is_critical: bool = Field(default=False, description="True iff Total Float <= 0")
    is_completed: bool = Field(default=False, description="True if activity was already verified completed")

    impact_severity: DownstreamImpactSeverity = Field(
        description="Classification of delay impact on this successor (ADR-016)",
    )
    available_float: int | None = Field(
        default=None,
        description="Total float buffer available prior to upstream delay absorption",
    )
    float_consumed: int = Field(
        ge=0,
        default=0,
        description="Number of float days consumed on this successor by upstream delay",
    )
    projected_delay_days: int = Field(
        ge=0,
        default=0,
        description="Net calendar delay forced onto successor after float exhaustion",
    )


# ==============================================================================
# Downstream Impact Result Model
# ==============================================================================

class DownstreamImpactResult(BaseModel):
    """
    Comprehensive evaluation of downstream impact for a source activity in the schedule DAG.
    """
    model_config = ConfigDict(extra="forbid")

    project_id: UUID = Field(description="Project tenant ID")
    source_activity_id: UUID = Field(description="Source activity ID")
    source_activity_code: str = Field(description="Source activity code")
    source_name: str = Field(description="Source activity name")
    source_delay_days: int = Field(description="Factual schedule delay of source activity in days")
    is_source_critical: bool = Field(description="True if source activity is on baseline critical path")

    total_downstream_activities_count: int = Field(ge=0, description="Count of unique reachable successors")
    critical_slippage_count: int = Field(ge=0, description="Count of successors suffering critical delay")
    buffer_absorbed_count: int = Field(ge=0, description="Count of successors absorbing delay via float")
    historical_completed_count: int = Field(ge=0, description="Count of completed downstream successors")

    impacted_successors: list[ImpactedSuccessorNode] = Field(
        description="Deduplicated list of reachable downstream successors in deterministic order",
    )
