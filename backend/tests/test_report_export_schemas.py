"""
Unit tests for Report Export Schemas (Phase 10.2).
Verifies Pydantic v2 schemas, enum definitions, and extra field rejection.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.export import (
    ExportDatasetType,
    ExportFormat,
    ExportMetadataResponse,
    ExportResult,
)


def test_export_format_enum():
    """Verifies supported export format enum values."""
    assert ExportFormat.CSV.value == "csv"
    assert ExportFormat.JSON.value == "json"
    assert len(ExportFormat) == 2


def test_export_dataset_type_enum():
    """Verifies canonical export dataset enum values."""
    assert ExportDatasetType.APPROVED_ACTUALS.value == "approved_actuals"
    assert ExportDatasetType.VARIANCE.value == "variance"
    assert ExportDatasetType.RISK_REGISTER.value == "risk_register"
    assert len(ExportDatasetType) == 3


def test_export_result_valid():
    """Verifies ExportResult validation and frozen configuration."""
    now = datetime.now(timezone.utc)
    proj_id = uuid4()

    res = ExportResult(
        content_type="text/csv; charset=utf-8",
        filename=f"approved_actuals_{proj_id}.csv",
        data="id,project_id\n1,2\n",
        record_count=1,
        dataset=ExportDatasetType.APPROVED_ACTUALS,
        format=ExportFormat.CSV,
        generated_at=now,
    )
    assert res.content_type == "text/csv; charset=utf-8"
    assert res.record_count == 1
    assert res.dataset == ExportDatasetType.APPROVED_ACTUALS
    assert res.format == ExportFormat.CSV

    # Verify frozen immutability
    with pytest.raises(ValidationError):
        res.record_count = 5


def test_export_result_extra_forbidden():
    """Verifies that extra fields are rejected on ExportResult."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ExportResult(
            content_type="text/csv",
            filename="test.csv",
            data="header\n",
            record_count=0,
            dataset=ExportDatasetType.VARIANCE,
            format=ExportFormat.CSV,
            generated_at=now,
            unauthorized_field="malicious",
        )


def test_export_metadata_response():
    """Verifies ExportMetadataResponse validation and immutability."""
    now = datetime.now(timezone.utc)
    proj_id = uuid4()

    meta = ExportMetadataResponse(
        project_id=proj_id,
        dataset=ExportDatasetType.RISK_REGISTER,
        format=ExportFormat.JSON,
        record_count=42,
        generated_at=now,
        filename=f"risk_register_{proj_id}.json",
        content_type="application/json; charset=utf-8",
    )
    assert meta.record_count == 42
    assert meta.dataset == ExportDatasetType.RISK_REGISTER
    assert meta.format == ExportFormat.JSON
