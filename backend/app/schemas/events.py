"""
Pydantic schemas for Field Events domain.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class FieldEventStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    MATCHED = "matched"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class FieldEventCreate(BaseModel):
    """Payload for manually recording/creating a field event."""
    model_config = ConfigDict(extra="forbid")

    report_id: str | None = Field(default=None, description="Optional linked source report ID")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event category")
    description: str = Field(..., min_length=1, max_length=1000, description="Description of work performed")
    discipline: str = Field(..., min_length=1, max_length=100, description="Discipline (Piping, Civil, Electrical, etc.)")
    location: str = Field(..., min_length=1, max_length=255, description="Physical location / area on site")
    event_date: date = Field(..., description="Date event occurred")
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage between 0 and 100")


class FieldEventUpdate(BaseModel):
    """Payload for updating an existing field event."""
    model_config = ConfigDict(extra="forbid")

    event_type: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    discipline: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    event_date: date | None = None
    progress_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    status: FieldEventStatus | None = None


class FieldEventResponse(BaseModel):
    """Serialized field event response model."""
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    report_id: str | None = None
    report_name: str | None = None
    event_type: str
    description: str
    discipline: str
    location: str
    event_date: date
    progress_percent: float
    status: FieldEventStatus
    extracted_by: str | None = None
    created_at: datetime
    updated_at: datetime


class FieldEventListResponse(BaseModel):
    """List response for field events."""
    model_config = ConfigDict(frozen=True)

    events: list[FieldEventResponse]
    total: int
