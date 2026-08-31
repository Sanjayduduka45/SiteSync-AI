"""
SiteSync AI — Phase 10.2 Report Export Schemas.
Data contracts and models defining supported export formats, dataset types,
and serialization metadata (ADR-019).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(str, Enum):
    """Supported export serialization formats per ADR-019."""
    CSV = "csv"
    JSON = "json"


class ExportDatasetType(str, Enum):
    """Canonical datasets available for report export."""
    APPROVED_ACTUALS = "approved_actuals"
    VARIANCE = "variance"
    RISK_REGISTER = "risk_register"


class ExportMetadataResponse(BaseModel):
    """Metadata envelope for an exported dataset."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    dataset: ExportDatasetType
    format: ExportFormat
    record_count: int
    generated_at: datetime
    filename: str
    content_type: str


class ExportResult(BaseModel):
    """Container for serialized export payload and response headers."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    content_type: str
    filename: str
    data: str
    record_count: int
    dataset: ExportDatasetType
    format: ExportFormat
    generated_at: datetime
