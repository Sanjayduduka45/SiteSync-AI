"""
Pydantic v2 schemas for AI Extractions domain — SiteSync AI Phase 5.
Defines models for structured entity extraction from raw field inputs.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExtractedActivity(BaseModel):
    """Discrete construction activity entity extracted from field notes/transcripts."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Verbatim or summary description of physical work performed",
    )
    progress_value: float | None = Field(
        default=None,
        description="Numerical progress quantity or percentage",
    )
    progress_unit: str | None = Field(
        default=None,
        max_length=50,
        description="Unit of measurement (e.g. m, m3, LF, CY, %, spools, tons)",
    )
    discipline: str | None = Field(
        default=None,
        max_length=100,
        description="Construction trade discipline (e.g. Piping, Civil, Electrical)",
    )
    location: str | None = Field(
        default=None,
        max_length=255,
        description="Site location, unit, area, or grid reference",
    )
    event_date: date | None = Field(
        default=None,
        description="Date work occurred on site",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="List of identified blockers, delays, or physical constraints",
    )
    evidence_tokens: list[str] = Field(
        default_factory=list,
        description="Verbatim source text fragments justifying this activity extraction",
    )

    @field_validator("description")
    @classmethod
    def validate_description_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Activity description cannot be empty or whitespace only")
        return v.strip()


class ExtractionResult(BaseModel):
    """Structured extraction payload produced by AI pipeline from a raw field input."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_input_id: UUID = Field(
        ...,
        description="Foreign key UUID referencing the parent field_inputs record",
    )
    extracted_activities: list[ExtractedActivity] = Field(
        default_factory=list,
        description="List of structured activities detected in the input",
    )
    extraction_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model-relative extraction confidence score between 0.0 and 1.0",
    )
    model_version: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of LLM and prompt template version used",
    )
    processing_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when extraction was processed",
    )

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Deterministic classification of confidence score per AI_SPEC policy."""
        if self.extraction_confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif self.extraction_confidence >= 0.60:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    @field_validator("model_version")
    @classmethod
    def validate_model_version_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Model version cannot be empty or whitespace only")
        return v.strip()


class ExtractionResponse(BaseModel):
    """Serialized representation of a stored public.ai_extractions database record."""
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    field_input_id: str
    status: ExtractionStatus = ExtractionStatus.PENDING
    extracted_data: ExtractionResult | dict[str, Any] = Field(default_factory=dict)
    confidence_score: float | None = None
    model_version: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ExtractionListResponse(BaseModel):
    """List response for AI extraction records."""
    model_config = ConfigDict(frozen=True)

    extractions: list[ExtractionResponse]
    total: int
