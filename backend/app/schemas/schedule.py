"""
SiteSync AI — Phase 6.2 Schedule and Matching Pydantic Schemas.
Canonical backend data contracts for:
  - Schedule activity creation, update, response, and listing
  - Activity embedding lifecycle metadata
  - Scoring breakdown and alternative match candidates
  - Match recommendation response and list wrappers
Strictly enforces extra="forbid" to reject unauthorized downstream fields.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MatchConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScheduleActivityCreate(BaseModel):
    """Payload for creating a new project schedule activity."""
    model_config = ConfigDict(extra="forbid")

    activity_code: str = Field(..., description="Project-unique activity code (e.g. ACT-1001)")
    name: str = Field(..., description="Human-readable title or description of the activity")
    wbs_code: Optional[str] = Field(None, description="Work Breakdown Structure code (e.g. 1.2.4)")
    discipline: Optional[str] = Field(None, description="Construction discipline / trade (e.g. Piping, Civil)")
    location: Optional[str] = Field(None, description="Physical site area / grid / unit reference")
    planned_start_date: Optional[date] = Field(None, description="Baseline planned start date")
    planned_finish_date: Optional[date] = Field(None, description="Baseline planned completion date")
    planned_quantity: Optional[float] = Field(None, ge=0.0, description="Planned physical work quantity")
    planned_unit: Optional[str] = Field(None, description="Unit of measure (e.g. LF, m3, spools)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extensible JSON metadata")

    @field_validator("activity_code", "name")
    @classmethod
    def validate_non_blank(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must not be empty or whitespace only")
        return v.strip()

    @field_validator("wbs_code", "discipline", "location", "planned_unit")
    @classmethod
    def strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None

    @model_validator(mode="after")
    def validate_date_ordering(self) -> ScheduleActivityCreate:
        if self.planned_start_date is not None and self.planned_finish_date is not None:
            if self.planned_start_date > self.planned_finish_date:
                raise ValueError(
                    f"planned_start_date ({self.planned_start_date}) must not be later than "
                    f"planned_finish_date ({self.planned_finish_date})"
                )
        return self


class ScheduleActivityResponse(BaseModel):
    """Response model representing a persisted schedule activity."""
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    activity_code: str
    name: str
    wbs_code: Optional[str] = None
    discipline: Optional[str] = None
    location: Optional[str] = None
    planned_start_date: Optional[date] = None
    planned_finish_date: Optional[date] = None
    planned_quantity: Optional[float] = None
    planned_unit: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ScheduleActivityListResponse(BaseModel):
    """Paginated collection response for schedule activities."""
    model_config = ConfigDict(extra="forbid")

    items: list[ScheduleActivityResponse]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class ActivityEmbeddingMetadata(BaseModel):
    """Metadata representing the lifecycle and hash state of an activity embedding."""
    model_config = ConfigDict(extra="forbid")

    schedule_activity_id: UUID
    project_id: UUID
    content_hash: str = Field(..., description="SHA-256 hash of embedded activity text")
    created_at: datetime
    updated_at: datetime


class ScoringBreakdown(BaseModel):
    """Multi-factor breakdown explaining contextual match recommendation score."""
    model_config = ConfigDict(extra="forbid")

    semantic_similarity: float = Field(..., ge=0.0, le=1.0, description="Raw cosine similarity (0.0 - 1.0)")
    discipline_contribution: float = Field(0.0, ge=0.0, le=1.0, description="Score component from trade alignment")
    location_contribution: float = Field(0.0, ge=0.0, le=1.0, description="Score component from location proximity")
    temporal_contribution: float = Field(0.0, ge=0.0, le=1.0, description="Score component from date window overlap")


class AlternativeMatch(BaseModel):
    """Candidate schedule activity considered during AI matching."""
    model_config = ConfigDict(extra="forbid")

    schedule_activity_id: UUID
    activity_code: str
    activity_name: str
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall match confidence")
    discipline: Optional[str] = None
    location: Optional[str] = None
    planned_start_date: Optional[date] = None
    planned_finish_date: Optional[date] = None
    scoring_breakdown: Optional[ScoringBreakdown] = None


class MatchRecommendationResponse(BaseModel):
    """Full match recommendation result for an extracted activity item."""
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    extraction_id: UUID
    activity_index: int = Field(0, ge=0, description="Index of activity in source extraction")
    recommended_activity_id: UUID
    recommended_activity_code: Optional[str] = None
    recommended_activity_name: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Composite confidence score")
    scoring_breakdown: ScoringBreakdown = Field(default_factory=lambda: ScoringBreakdown(semantic_similarity=0.0))
    alternative_matches: list[AlternativeMatch] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @property
    def confidence_level(self) -> MatchConfidenceLevel:
        """Pure schema classification of confidence bands defined by AI_SPEC."""
        if self.confidence_score >= 0.85:
            return MatchConfidenceLevel.HIGH
        elif self.confidence_score >= 0.60:
            return MatchConfidenceLevel.MEDIUM
        return MatchConfidenceLevel.LOW


class MatchRecommendationListResponse(BaseModel):
    """Collection wrapper for match recommendations."""
    model_config = ConfigDict(extra="forbid")

    items: list[MatchRecommendationResponse]
    total: int = Field(..., ge=0)
