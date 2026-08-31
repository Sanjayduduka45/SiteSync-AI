"""
SiteSync AI — Phase 7.2 Planner Review & Human Decision Schemas.
Canonical backend data contracts for:
  - Approve match request
  - Reject match request with mandatory justification
  - Modify match request with schedule activity override
  - Planner decision response (audit trail record)
  - Approved actual response and paginated collection
Strictly enforces extra="forbid" to reject unauthorized downstream fields.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlannerDecisionType(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ApproveMatchRequest(BaseModel):
    """Payload for approving an AI match recommendation as-is."""
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None, description="Optional planner notes on approval")

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class RejectMatchRequest(BaseModel):
    """Payload for rejecting an AI match recommendation."""
    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(
        ...,
        description="Mandatory justification explaining why the AI match recommendation was rejected",
    )

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rejection_reason must not be empty or whitespace only")
        return v.strip()


class ModifyMatchRequest(BaseModel):
    """Payload for modifying an AI match recommendation before approval."""
    model_config = ConfigDict(extra="forbid")

    schedule_activity_id: UUID = Field(
        ...,
        description="Target schedule activity ID overridden by the planner",
    )
    actual_quantity: Optional[float] = Field(
        None,
        ge=0.0,
        description="Overridden actual physical progress quantity",
    )
    actual_unit: Optional[str] = Field(
        None,
        description="Overridden unit of measure",
    )
    actual_date: date = Field(
        ...,
        description="Verified date the progress occurred on site",
    )
    notes: Optional[str] = Field(
        None,
        description="Optional planner notes or reasoning for modification",
    )

    @field_validator("actual_unit", "notes")
    @classmethod
    def normalize_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class PlannerDecisionResponse(BaseModel):
    """Response model representing a human planner decision audit record."""
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    match_id: UUID
    extraction_id: UUID
    decision: PlannerDecisionType
    decided_by: UUID
    decided_at: datetime
    rejection_reason: Optional[str] = None
    original_payload: dict[str, Any] = Field(default_factory=dict)
    modified_payload: Optional[dict[str, Any]] = None
    created_at: datetime


class ApprovedActualResponse(BaseModel):
    """Response model representing an official approved construction progress record."""
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    schedule_activity_id: UUID
    extraction_id: UUID
    match_id: UUID
    activity_index: int = Field(..., ge=0)
    actual_quantity: Optional[float] = Field(None, ge=0.0)
    actual_unit: Optional[str] = None
    actual_date: date
    source_evidence: list[Any] = Field(default_factory=list)
    approved_by: UUID
    approved_at: datetime
    notes: Optional[str] = None
    is_modified: bool = False
    created_at: datetime
    updated_at: datetime


class ApprovedActualListResponse(BaseModel):
    """Paginated collection response for official approved actual progress records."""
    model_config = ConfigDict(extra="forbid")

    items: list[ApprovedActualResponse]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
