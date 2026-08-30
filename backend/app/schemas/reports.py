"""
Pydantic schemas for Reports domain.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class ReportStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ReportCreate(BaseModel):
    """Payload for creating/uploading a report record."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="User-friendly report name")
    file_name: str = Field(..., min_length=1, max_length=255, description="Original filename")
    file_type: str = Field(..., min_length=1, max_length=50, description="File MIME or extension (pdf, xlsx, csv, txt)")
    file_size: int = Field(default=0, ge=0, description="File size in bytes")
    source: str = Field(default="manual_upload", max_length=50, description="Source origin")


class ReportResponse(BaseModel):
    """Serialized report response model."""
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    name: str
    file_name: str
    file_type: str
    file_size: int
    source: str
    status: ReportStatus
    uploaded_by: str | None = None
    uploaded_by_email: str | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    """Paginated or listed reports response."""
    model_config = ConfigDict(frozen=True)

    reports: list[ReportResponse]
    total: int
