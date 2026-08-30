"""
Pydantic schemas for Field Inputs domain — SiteSync AI Phase 4.
Defines models for raw multi-modal field submissions (text, voice, photo, document).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class FieldInputType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"
    DOCUMENT = "document"


class TranscriptionStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TextInputCreate(BaseModel):
    """Payload for submitting a raw text note from the field."""
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255, description="Optional brief title")
    raw_text: str = Field(..., min_length=1, max_length=20000, description="Raw notes, observations, or progress details")
    field_date: date = Field(default_factory=date.today, description="Date work occurred")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional custom metadata")


class FieldInputResponse(BaseModel):
    """Serialized representation of a stored field input."""
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    submitted_by: str
    submitted_by_email: str | None = None
    input_type: FieldInputType
    title: str | None = None
    raw_text: str | None = None
    media_path: str | None = None
    media_filename: str | None = None
    media_mime_type: str | None = None
    media_size_bytes: int = 0
    media_url: str | None = None
    audio_duration_seconds: float | None = None
    transcription_status: TranscriptionStatus = TranscriptionStatus.NONE
    transcription_error: str | None = None
    field_date: date
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class FieldInputListResponse(BaseModel):
    """List response for field inputs."""
    model_config = ConfigDict(frozen=True)

    inputs: list[FieldInputResponse]
    total: int
