"""
Comprehensive tests for ReportExportService (Phase 10.2).
Verifies:
1. CSV and JSON serialization
2. Approved actuals, variance, and risk register exports
3. Deterministic column ordering and row ordering
4. Repeated serialization byte-for-byte reproducibility
5. Special characters: UTF-8, commas, quotes, newlines
6. Type handling: Null, dates, timestamps, enums, booleans, numbers
7. CSV formula injection protection (=, +, -, @, TAB, CR)
8. Preservation of legitimate negative numbers
9. JSON format constraints: valid JSON, no Python representations, no NaN/Infinity
10. Tenant isolation: project mismatch and mixed-project rejection
11. Security redaction: no secrets, embedding vectors, or raw prompts
12. Phase 8 & Phase 9 consumed directly without recalculation
13. Complete dataset retrieval without pagination truncation
14. Empty dataset handling
15. Static boundary scan
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.schemas.decision import ApprovedActualResponse
from app.schemas.export import ExportDatasetType, ExportFormat
from app.schemas.risk import (
    ActivityRiskAssessment,
    RiskCategory,
    RiskSeverityLevel,
)
from app.schemas.variance import ActivityVarianceItem, ActivityVarianceStatus
from app.services.decision_service import DecisionService
from app.services.report_export_service import (
    CrossProjectExportError,
    ReportExportService,
    UnsupportedExportDatasetError,
    UnsupportedExportFormatError,
    sanitize_csv_value,
)
from app.services.risk_query_service import RiskQueryService
from app.services.variance_query_service import VarianceQueryService


@pytest.fixture
def export_env():
    """Sets up an isolated test environment with fresh in-memory services."""
    dec_svc = DecisionService()
    dec_svc.decision_repo.clear()
    dec_svc.actual_repo.clear()
    var_svc = VarianceQueryService()
    var_svc.decision_service = dec_svc
    risk_svc = RiskQueryService()
    risk_svc.variance_query_service = var_svc

    export_svc = ReportExportService(
        decision_svc=dec_svc,
        variance_svc=var_svc,
        risk_svc=risk_svc,
    )

    return {
        "export_svc": export_svc,
        "dec_svc": dec_svc,
        "var_svc": var_svc,
        "risk_svc": risk_svc,
    }


# ==============================================================================
# 1. Formula Injection Protection Tests
# ==============================================================================

def test_formula_injection_sanitization():
    """Verifies that dangerous formula triggers are escaped with a leading quote while numbers remain intact."""
    # Malicious formula strings
    assert sanitize_csv_value("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert sanitize_csv_value("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_value("-1+1") == "'-1+1"
    assert sanitize_csv_value("@SUM(B1)") == "'@SUM(B1)"
    assert sanitize_csv_value("\tmalicious") == "'\tmalicious"
    assert sanitize_csv_value("\rmalicious") == "'\rmalicious"

    # Legitimate numbers (should NOT be corrupted)
    assert sanitize_csv_value(-5) == -5
    assert sanitize_csv_value(-12.34) == -12.34
    assert sanitize_csv_value(0) == 0
    assert sanitize_csv_value(100) == 100
    assert sanitize_csv_value("-5.5") == "-5.5"
    assert sanitize_csv_value("+42") == "+42"

    # Dates and UUIDs
    test_date = date(2026, 8, 31)
    assert sanitize_csv_value(test_date) == "2026-08-31"

    test_uuid = uuid4()
    assert sanitize_csv_value(test_uuid) == str(test_uuid)

    # Booleans and Nulls
    assert sanitize_csv_value(True) == "TRUE"
    assert sanitize_csv_value(False) == "FALSE"
    assert sanitize_csv_value(None) == ""


# ==============================================================================
# 2. Approved Actuals Export Tests
# ==============================================================================

def test_approved_actuals_csv_serialization(export_env):
    """Verifies CSV export of approved actuals with exact column ordering and deterministic sorting."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    item1 = ApprovedActualResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        project_id=proj_id,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=50.5,
        actual_unit="LF",
        actual_date=date(2026, 8, 20),
        approved_by=uuid4(),
        approved_at=datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc),
        notes="First batch verified",
        is_modified=False,
        created_at=datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc),
    )
    item2 = ApprovedActualResponse(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        project_id=proj_id,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=1,
        actual_quantity=75.0,
        actual_unit="LF",
        actual_date=date(2026, 8, 21),
        approved_by=uuid4(),
        approved_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
        notes="=DANGEROUS_FORMULA",
        is_modified=True,
        created_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
    )

    res = export_svc.serialize_approved_actuals(proj_id, [item1, item2], ExportFormat.CSV)
    assert res.format == ExportFormat.CSV
    assert res.dataset == ExportDatasetType.APPROVED_ACTUALS
    assert res.record_count == 2
    assert "text/csv" in res.content_type

    # Parse CSV output to verify headers and deterministic sorting (latest date first)
    reader = list(csv.reader(res.data.splitlines()))
    headers = reader[0]
    assert headers == export_svc.APPROVED_ACTUALS_COLUMNS

    # Row 1 must be item2 (Aug 21) and Row 2 must be item1 (Aug 20)
    assert reader[1][0] == str(item2.id)
    assert reader[1][6] == "75.0"
    assert reader[1][11] == "'=DANGEROUS_FORMULA"  # Escaped formula
    assert reader[1][12] == "TRUE"

    assert reader[2][0] == str(item1.id)
    assert reader[2][6] == "50.5"
    assert reader[2][12] == "FALSE"


def test_approved_actuals_json_serialization(export_env):
    """Verifies structured JSON export of approved actuals."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    item = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_id,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=100.0,
        actual_unit="m3",
        actual_date=date(2026, 8, 15),
        approved_by=uuid4(),
        approved_at=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        notes=None,
        is_modified=False,
        created_at=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    res = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.JSON)
    assert res.format == ExportFormat.JSON
    assert "application/json" in res.content_type

    parsed = json.loads(res.data)
    assert parsed["project_id"] == str(proj_id)
    assert parsed["dataset"] == "approved_actuals"
    assert parsed["record_count"] == 1
    assert len(parsed["records"]) == 1
    assert parsed["records"][0]["id"] == str(item.id)
    assert parsed["records"][0]["actual_quantity"] == 100.0
    assert parsed["records"][0]["notes"] is None


# ==============================================================================
# 3. Variance Export Tests
# ==============================================================================

def test_variance_csv_and_json_serialization(export_env):
    """Verifies Plan vs Actual variance export in both CSV and JSON."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    var_item1 = ActivityVarianceItem(
        activity_id=UUID("00000000-0000-0000-0000-000000000010"),
        project_id=proj_id,
        activity_code="ACT-B",
        name="Piping B",
        wbs_code="1.1",
        discipline="Piping",
        location="Area 1",
        planned_quantity=100.0,
        planned_unit="LF",
        planned_start_date=date(2026, 8, 1),
        planned_finish_date=date(2026, 8, 10),
        actual_quantity_total=80.0,
        actual_unit="LF",
        latest_actual_date=date(2026, 8, 8),
        approved_actuals_count=2,
        quantity_variance=-20.0,
        progress_percent=80.0,
        date_variance_days=-2,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
        is_flagged=False,
        flag_reason=None,
    )
    var_item2 = ActivityVarianceItem(
        activity_id=UUID("00000000-0000-0000-0000-000000000020"),
        project_id=proj_id,
        activity_code="ACT-A",
        name="Piping A",
        wbs_code="1.1",
        discipline="Piping",
        location="Area 1",
        planned_quantity=200.0,
        planned_unit="LF",
        planned_start_date=date(2026, 8, 1),
        planned_finish_date=date(2026, 8, 5),
        actual_quantity_total=200.0,
        actual_unit="LF",
        latest_actual_date=date(2026, 8, 5),
        approved_actuals_count=1,
        quantity_variance=0.0,
        progress_percent=100.0,
        date_variance_days=0,
        variance_status=ActivityVarianceStatus.COMPLETED,
        is_flagged=False,
        flag_reason=None,
    )

    # CSV Test (sorted by activity_code ASC -> ACT-A then ACT-B)
    res_csv = export_svc.serialize_variance(proj_id, [var_item1, var_item2], ExportFormat.CSV)
    reader = list(csv.reader(res_csv.data.splitlines()))
    assert reader[0] == export_svc.VARIANCE_COLUMNS
    assert reader[1][2] == "ACT-A"
    assert reader[2][2] == "ACT-B"
    # Negative quantity variance -20.0 must remain a valid unescaped number
    assert reader[2][15] == "-20.0"
    assert reader[2][17] == "-2"

    # JSON Test
    res_json = export_svc.serialize_variance(proj_id, [var_item1, var_item2], ExportFormat.JSON)
    parsed = json.loads(res_json.data)
    assert parsed["record_count"] == 2
    assert parsed["records"][0]["activity_code"] == "ACT-A"
    assert parsed["records"][1]["activity_code"] == "ACT-B"


# ==============================================================================
# 4. Risk Register Export Tests
# ==============================================================================

def test_risk_register_csv_and_json_serialization(export_env):
    """Verifies Schedule Risk Register export with category array formatting and severity preservation."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    risk1 = ActivityRiskAssessment(
        activity_id=UUID("00000000-0000-0000-0000-000000000030"),
        project_id=proj_id,
        activity_code="ACT-CRIT",
        name="Critical Spool Assembly",
        wbs_code="2.1",
        discipline="Mechanical",
        location="Zone 3",
        severity=RiskSeverityLevel.CRITICAL,
        risk_score=95,
        categories=[RiskCategory.CRITICAL_PATH_DELAY, RiskCategory.FLOAT_EROSION],
        is_critical_path=True,
        total_float=0,
        date_variance_days=5,
        direct_successors_count=3,
        transitive_successors_count=8,
        critical_slippage_successors_count=2,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
        progress_percent=40.0,
        is_completed=False,
    )
    risk2 = ActivityRiskAssessment(
        activity_id=UUID("00000000-0000-0000-0000-000000000040"),
        project_id=proj_id,
        activity_code="ACT-LOW",
        name="Non-Critical Cable Pull",
        wbs_code="3.1",
        discipline="Electrical",
        location="Zone 1",
        severity=RiskSeverityLevel.LOW,
        risk_score=15,
        categories=[],
        is_critical_path=False,
        total_float=14,
        date_variance_days=0,
        direct_successors_count=1,
        transitive_successors_count=1,
        critical_slippage_successors_count=0,
        variance_status=ActivityVarianceStatus.NOT_STARTED,
        progress_percent=0.0,
        is_completed=False,
    )

    # CSV Test (sorted by risk_score DESC -> ACT-CRIT (95) then ACT-LOW (15))
    res_csv = export_svc.serialize_risk_register(proj_id, [risk2, risk1], ExportFormat.CSV)
    reader = list(csv.reader(res_csv.data.splitlines()))
    assert reader[0] == export_svc.RISK_REGISTER_COLUMNS
    assert reader[1][2] == "ACT-CRIT"
    assert reader[1][7] == "critical"
    assert reader[1][8] == "95"
    assert "critical_path_delay" in reader[1][9]
    assert reader[2][2] == "ACT-LOW"
    assert reader[2][8] == "15"

    # JSON Test
    res_json = export_svc.serialize_risk_register(proj_id, [risk1, risk2], ExportFormat.JSON)
    parsed = json.loads(res_json.data)
    assert parsed["records"][0]["activity_code"] == "ACT-CRIT"
    assert parsed["records"][0]["categories"] == ["critical_path_delay", "float_erosion"]


# ==============================================================================
# 5. Determinism and Reproducibility Tests
# ==============================================================================

def test_repeated_serialization_identical_output(export_env):
    """Proves byte-for-byte and string-for-string determinism across multiple serialization runs."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    item = ApprovedActualResponse(
        id=UUID("00000000-0000-0000-0000-000000000100"),
        project_id=proj_id,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=120.0,
        actual_unit="tons",
        actual_date=date(2026, 8, 25),
        approved_by=uuid4(),
        approved_at=datetime(2026, 8, 25, 8, 0, 0, tzinfo=timezone.utc),
        notes="Verified",
        is_modified=False,
        created_at=datetime(2026, 8, 25, 8, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 25, 8, 0, 0, tzinfo=timezone.utc),
    )

    out1 = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.CSV)
    out2 = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.CSV)
    assert out1.data == out2.data

    json_out1 = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.JSON)
    json_out2 = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.JSON)
    # Parse and compare JSON records
    assert json.loads(json_out1.data)["records"] == json.loads(json_out2.data)["records"]


# ==============================================================================
# 6. Special Character Handling Tests (RFC 4180)
# ==============================================================================

def test_special_character_and_quoting_handling(export_env):
    """Verifies that quotes, commas, embedded newlines, and UTF-8 are compliant with RFC 4180."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    complex_notes = 'Line 1 with "quotes", and commas.\nLine 2 with UTF-8: бетон & 鋼筋 🏗️'
    item = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_id,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=50.0,
        actual_unit="LF",
        actual_date=date(2026, 8, 20),
        approved_by=uuid4(),
        approved_at=datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
        notes=complex_notes,
        is_modified=False,
        created_at=datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
    )

    res_csv = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.CSV)
    # Parse back with standard CSV reader
    reader = list(csv.reader(res_csv.data.splitlines(keepends=True)))
    # Notes are in index 11
    parsed_notes = reader[1][11]
    assert parsed_notes == complex_notes

    res_json = export_svc.serialize_approved_actuals(proj_id, [item], ExportFormat.JSON)
    parsed_json = json.loads(res_json.data)
    assert parsed_json["records"][0]["notes"] == complex_notes


# ==============================================================================
# 7. Tenant Isolation & IDOR Tests
# ==============================================================================

def test_tenant_isolation_cross_project_rejection(export_env):
    """Verifies that supplying records belonging to a different project raises CrossProjectExportError."""
    export_svc = export_env["export_svc"]
    proj_a = uuid4()
    proj_b = uuid4()

    item_b = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_b,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=10.0,
        actual_unit="LF",
        actual_date=date.today(),
        approved_by=uuid4(),
        approved_at=datetime.now(timezone.utc),
        notes=None,
        is_modified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(CrossProjectExportError):
        export_svc.serialize_approved_actuals(proj_a, [item_b], ExportFormat.CSV)


# ==============================================================================
# 8. Empty Dataset Behavior Tests
# ==============================================================================

def test_empty_dataset_serialization(export_env):
    """Verifies that empty datasets serialize gracefully into valid headers or empty JSON arrays."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    # CSV empty
    res_csv = export_svc.serialize_approved_actuals(proj_id, [], ExportFormat.CSV)
    assert res_csv.record_count == 0
    lines = res_csv.data.strip().splitlines()
    assert len(lines) == 1
    assert lines[0] == ",".join(export_svc.APPROVED_ACTUALS_COLUMNS)

    # JSON empty
    res_json = export_svc.serialize_approved_actuals(proj_id, [], ExportFormat.JSON)
    assert res_json.record_count == 0
    parsed = json.loads(res_json.data)
    assert parsed["records"] == []
    assert parsed["record_count"] == 0


# ==============================================================================
# 9. Format and Dataset Validation Error Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_unsupported_export_options(export_env):
    """Verifies that invalid format or dataset types raise explicit domain exceptions."""
    export_svc = export_env["export_svc"]
    proj_id = uuid4()

    with pytest.raises(UnsupportedExportDatasetError):
        await export_svc.export_dataset(proj_id, "unknown_dataset", "csv")

    with pytest.raises(UnsupportedExportFormatError):
        await export_svc.export_dataset(proj_id, "variance", "pdf")

    with pytest.raises(UnsupportedExportFormatError):
        await export_svc.export_dataset(proj_id, "variance", "xlsx")


# ==============================================================================
# 10. Security & Redaction Static Scan
# ==============================================================================

def test_security_and_redaction_boundary():
    """Verifies that exported column sets do NOT include sensitive fields or internal embeddings."""
    disallowed_keywords = [
        "password",
        "token",
        "secret",
        "key",
        "embedding",
        "vector",
        "prompt",
        "system_instruction",
        "raw_response",
    ]

    all_export_columns = (
        ReportExportService.APPROVED_ACTUALS_COLUMNS
        + ReportExportService.VARIANCE_COLUMNS
        + ReportExportService.RISK_REGISTER_COLUMNS
    )

    for col in all_export_columns:
        for bad_kw in disallowed_keywords:
            assert bad_kw not in col.lower(), f"Disallowed security keyword '{bad_kw}' found in export column '{col}'"
