"""
SiteSync AI — Phase 10.2 Report Export Serialization Service.
Implements deterministic, RFC 4180-compliant CSV serialization with formula injection
mitigation and structured JSON serialization across canonical datasets (ADR-019).
Strictly read-only, multi-tenant scoped, and pure of analytic recalculation.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from app.schemas.decision import ApprovedActualResponse
from app.schemas.export import (
    ExportDatasetType,
    ExportFormat,
    ExportResult,
)
from app.schemas.risk import ActivityRiskAssessment
from app.schemas.variance import ActivityVarianceItem
from app.services.decision_service import DecisionService, decision_service
from app.services.risk_query_service import RiskQueryService, risk_query_service
from app.services.variance_query_service import VarianceQueryService, variance_query_service

logger = logging.getLogger(__name__)

# CSV formula injection trigger characters
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _parse_uuid(val: str | UUID) -> UUID:
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


class ExportError(Exception):
    """Base exception for report export domain errors."""
    pass


class UnsupportedExportFormatError(ExportError):
    """Raised when an unrecognized export serialization format is requested."""
    pass


class UnsupportedExportDatasetError(ExportError):
    """Raised when an unrecognized export dataset is requested."""
    pass


class CrossProjectExportError(ExportError):
    """Raised when records belonging to multiple projects are supplied to a project export."""
    pass


class InvalidExportDataError(ExportError):
    """Raised when input records are malformed or invalid for export serialization."""
    pass


def sanitize_csv_value(val: Any) -> Any:
    """
    Applies formula injection protection per ADR-019 for CSV serialization.
    Prepends a single quote `'` to text values starting with `=`, `+`, `-`, `@`, `\\t`, or `\\r`.
    Preserves legitimate negative/positive numeric types, dates, and UUIDs without corruption.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, (list, set, tuple)):
        # Format list elements cleanly
        items_str = [x.value if hasattr(x, "value") else str(x) for x in val]
        s = "; ".join(items_str)
    else:
        s = str(val)

    # Check for formula injection triggers on text
    if any(s.startswith(p) for p in FORMULA_PREFIXES):
        # Allow legitimate numbers formatted as strings
        try:
            float(s)
            return s
        except ValueError:
            pass
        return f"'{s}"
    return s


class ReportExportService:
    """
    Orchestrates dataset retrieval and deterministic serialization into CSV and JSON.
    Acts as a pure serializer: consumes verified domain metrics without recalculating math.
    """

    APPROVED_ACTUALS_COLUMNS = [
        "id",
        "project_id",
        "schedule_activity_id",
        "extraction_id",
        "match_id",
        "activity_index",
        "actual_quantity",
        "actual_unit",
        "actual_date",
        "approved_by",
        "approved_at",
        "notes",
        "is_modified",
        "created_at",
        "updated_at",
    ]

    VARIANCE_COLUMNS = [
        "activity_id",
        "project_id",
        "activity_code",
        "name",
        "wbs_code",
        "discipline",
        "location",
        "planned_quantity",
        "planned_unit",
        "planned_start_date",
        "planned_finish_date",
        "actual_quantity_total",
        "actual_unit",
        "latest_actual_date",
        "approved_actuals_count",
        "quantity_variance",
        "progress_percent",
        "date_variance_days",
        "variance_status",
        "is_flagged",
        "flag_reason",
    ]

    RISK_REGISTER_COLUMNS = [
        "activity_id",
        "project_id",
        "activity_code",
        "name",
        "wbs_code",
        "discipline",
        "location",
        "severity",
        "risk_score",
        "categories",
        "is_critical_path",
        "total_float",
        "date_variance_days",
        "direct_successors_count",
        "transitive_successors_count",
        "critical_slippage_successors_count",
        "variance_status",
        "progress_percent",
        "is_completed",
    ]

    def __init__(
        self,
        decision_svc: DecisionService | None = None,
        variance_svc: VarianceQueryService | None = None,
        risk_svc: RiskQueryService | None = None,
    ) -> None:
        self.decision_service = decision_svc or decision_service
        self.variance_query_service = variance_svc or variance_query_service
        self.risk_query_service = risk_svc or risk_query_service

    # ==============================================================================
    # High-Level Orchestrated Export Methods (Full Dataset Retrieval)
    # ==============================================================================

    async def export_dataset(
        self,
        project_id: str | UUID,
        dataset_type: str | ExportDatasetType,
        export_format: str | ExportFormat,
    ) -> ExportResult:
        """
        Orchestrates full dataset retrieval and serialization for a project.
        """
        proj_uuid = _parse_uuid(project_id)

        if isinstance(dataset_type, str):
            try:
                ds_type = ExportDatasetType(dataset_type.lower())
            except ValueError:
                raise UnsupportedExportDatasetError(f"Unsupported export dataset type: '{dataset_type}'")
        else:
            ds_type = dataset_type

        if isinstance(export_format, str):
            try:
                fmt = ExportFormat(export_format.lower())
            except ValueError:
                raise UnsupportedExportFormatError(f"Unsupported export format: '{export_format}'")
        else:
            fmt = export_format

        if ds_type == ExportDatasetType.APPROVED_ACTUALS:
            return await self.export_approved_actuals(proj_uuid, fmt)
        elif ds_type == ExportDatasetType.VARIANCE:
            return await self.export_variance(proj_uuid, fmt)
        elif ds_type == ExportDatasetType.RISK_REGISTER:
            return await self.export_risk_register(proj_uuid, fmt)
        else:
            raise UnsupportedExportDatasetError(f"Unsupported export dataset type: '{ds_type}'")

    async def export_approved_actuals(
        self,
        project_id: str | UUID,
        export_format: ExportFormat = ExportFormat.CSV,
    ) -> ExportResult:
        """
        Retrieves the complete approved actuals dataset for a project and serializes it.
        """
        proj_uuid = _parse_uuid(project_id)
        # Fetch full dataset without pagination truncation
        records, _ = await self.decision_service.actual_repo.list_approved_actuals(
            project_id=str(proj_uuid),
            limit=100000,
            offset=0,
        )
        return self.serialize_approved_actuals(proj_uuid, records, export_format)

    async def export_variance(
        self,
        project_id: str | UUID,
        export_format: ExportFormat = ExportFormat.CSV,
    ) -> ExportResult:
        """
        Retrieves the complete Plan vs Actual variance dataset for a project and serializes it.
        """
        proj_uuid = _parse_uuid(project_id)
        # Retrieve full dataset without pagination truncation
        records = await self.variance_query_service._get_calculated_activity_items(
            project_id=str(proj_uuid)
        )
        return self.serialize_variance(proj_uuid, records, export_format)

    async def export_risk_register(
        self,
        project_id: str | UUID,
        export_format: ExportFormat = ExportFormat.CSV,
    ) -> ExportResult:
        """
        Retrieves the complete Schedule Risk Register dataset for a project and serializes it.
        """
        proj_uuid = _parse_uuid(project_id)
        # Retrieve full assessed risk summary without pagination truncation
        summary = await self.risk_query_service.get_project_risk_summary(
            project_id=str(proj_uuid)
        )
        return self.serialize_risk_register(proj_uuid, summary.items, export_format)

    # ==============================================================================
    # Pure Domain Serializers
    # ==============================================================================

    def serialize_approved_actuals(
        self,
        project_id: str | UUID,
        items: Sequence[ApprovedActualResponse],
        export_format: ExportFormat,
    ) -> ExportResult:
        """
        Pure serializer for Approved Actual progress records.
        """
        proj_uuid = _parse_uuid(project_id)
        self._validate_tenant_isolation(proj_uuid, items)

        # Deterministic Sort: actual_date DESC, approved_at DESC, id ASC
        sorted_items = sorted(
            items,
            key=lambda x: (
                -(x.actual_date.toordinal() if x.actual_date else 0),
                -(x.approved_at.timestamp() if x.approved_at else 0),
                str(x.id),
            ),
        )

        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d_%H%M%S")

        if export_format == ExportFormat.CSV:
            csv_data = self._to_csv(
                columns=self.APPROVED_ACTUALS_COLUMNS,
                rows=[self._approved_actual_to_dict(it) for it in sorted_items],
            )
            return ExportResult(
                content_type="text/csv; charset=utf-8",
                filename=f"approved_actuals_{proj_uuid}_{date_stamp}.csv",
                data=csv_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.APPROVED_ACTUALS,
                format=ExportFormat.CSV,
                generated_at=now,
            )
        elif export_format == ExportFormat.JSON:
            json_data = self._to_json(
                project_id=proj_uuid,
                dataset_type=ExportDatasetType.APPROVED_ACTUALS,
                records=[it.model_dump(mode="json") for it in sorted_items],
                generated_at=now,
            )
            return ExportResult(
                content_type="application/json; charset=utf-8",
                filename=f"approved_actuals_{proj_uuid}_{date_stamp}.json",
                data=json_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.APPROVED_ACTUALS,
                format=ExportFormat.JSON,
                generated_at=now,
            )
        else:
            raise UnsupportedExportFormatError(f"Unsupported export format: '{export_format}'")

    def serialize_variance(
        self,
        project_id: str | UUID,
        items: Sequence[ActivityVarianceItem],
        export_format: ExportFormat,
    ) -> ExportResult:
        """
        Pure serializer for Plan vs Actual variance records.
        """
        proj_uuid = _parse_uuid(project_id)
        self._validate_tenant_isolation(proj_uuid, items)

        # Deterministic Sort: activity_code ASC, activity_id ASC
        sorted_items = sorted(
            items,
            key=lambda x: (x.activity_code or "", str(x.activity_id)),
        )

        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d_%H%M%S")

        if export_format == ExportFormat.CSV:
            csv_data = self._to_csv(
                columns=self.VARIANCE_COLUMNS,
                rows=[self._variance_item_to_dict(it) for it in sorted_items],
            )
            return ExportResult(
                content_type="text/csv; charset=utf-8",
                filename=f"variance_{proj_uuid}_{date_stamp}.csv",
                data=csv_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.VARIANCE,
                format=ExportFormat.CSV,
                generated_at=now,
            )
        elif export_format == ExportFormat.JSON:
            json_data = self._to_json(
                project_id=proj_uuid,
                dataset_type=ExportDatasetType.VARIANCE,
                records=[it.model_dump(mode="json") for it in sorted_items],
                generated_at=now,
            )
            return ExportResult(
                content_type="application/json; charset=utf-8",
                filename=f"variance_{proj_uuid}_{date_stamp}.json",
                data=json_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.VARIANCE,
                format=ExportFormat.JSON,
                generated_at=now,
            )
        else:
            raise UnsupportedExportFormatError(f"Unsupported export format: '{export_format}'")

    def serialize_risk_register(
        self,
        project_id: str | UUID,
        items: Sequence[ActivityRiskAssessment],
        export_format: ExportFormat,
    ) -> ExportResult:
        """
        Pure serializer for Schedule Risk Register records.
        """
        proj_uuid = _parse_uuid(project_id)
        self._validate_tenant_isolation(proj_uuid, items)

        # Deterministic Sort: -risk_score, total_float ASC (nulls last), activity_code ASC, activity_id ASC
        sorted_items = sorted(
            items,
            key=lambda x: (
                -x.risk_score,
                x.total_float if x.total_float is not None else 999999,
                x.activity_code or "",
                str(x.activity_id),
            ),
        )

        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d_%H%M%S")

        if export_format == ExportFormat.CSV:
            csv_data = self._to_csv(
                columns=self.RISK_REGISTER_COLUMNS,
                rows=[self._risk_item_to_dict(it) for it in sorted_items],
            )
            return ExportResult(
                content_type="text/csv; charset=utf-8",
                filename=f"risk_register_{proj_uuid}_{date_stamp}.csv",
                data=csv_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.RISK_REGISTER,
                format=ExportFormat.CSV,
                generated_at=now,
            )
        elif export_format == ExportFormat.JSON:
            json_data = self._to_json(
                project_id=proj_uuid,
                dataset_type=ExportDatasetType.RISK_REGISTER,
                records=[it.model_dump(mode="json") for it in sorted_items],
                generated_at=now,
            )
            return ExportResult(
                content_type="application/json; charset=utf-8",
                filename=f"risk_register_{proj_uuid}_{date_stamp}.json",
                data=json_data,
                record_count=len(sorted_items),
                dataset=ExportDatasetType.RISK_REGISTER,
                format=ExportFormat.JSON,
                generated_at=now,
            )
        else:
            raise UnsupportedExportFormatError(f"Unsupported export format: '{export_format}'")

    # ==============================================================================
    # Private Formatting & Conversion Helpers
    # ==============================================================================

    def _validate_tenant_isolation(self, project_id: UUID, items: Sequence[Any]) -> None:
        """Ensures all records strictly match the requested project ID."""
        for item in items:
            item_proj_id = getattr(item, "project_id", None)
            if item_proj_id is not None and _parse_uuid(item_proj_id) != project_id:
                raise CrossProjectExportError(
                    f"Cross-project dataset error: record belongs to project '{item_proj_id}', "
                    f"expected '{project_id}'"
                )

    def _to_csv(self, columns: list[str], rows: list[dict[str, Any]]) -> str:
        """Renders RFC 4180-compliant CSV with formula injection escaping."""
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)

        # Write header
        writer.writerow(columns)

        # Write sanitized rows
        for row in rows:
            formatted_row = [sanitize_csv_value(row.get(col)) for col in columns]
            writer.writerow(formatted_row)

        return output.getvalue()

    def _to_json(
        self,
        project_id: UUID,
        dataset_type: ExportDatasetType,
        records: list[dict[str, Any]],
        generated_at: datetime,
    ) -> str:
        """Renders structured JSON with envelope metadata."""
        envelope = {
            "project_id": str(project_id),
            "dataset": dataset_type.value,
            "generated_at": generated_at.isoformat(),
            "record_count": len(records),
            "records": records,
        }
        return json.dumps(envelope, indent=2, ensure_ascii=False)

    def _approved_actual_to_dict(self, item: ApprovedActualResponse) -> dict[str, Any]:
        return {
            "id": item.id,
            "project_id": item.project_id,
            "schedule_activity_id": item.schedule_activity_id,
            "extraction_id": item.extraction_id,
            "match_id": item.match_id,
            "activity_index": item.activity_index,
            "actual_quantity": item.actual_quantity,
            "actual_unit": item.actual_unit,
            "actual_date": item.actual_date,
            "approved_by": item.approved_by,
            "approved_at": item.approved_at,
            "notes": item.notes,
            "is_modified": item.is_modified,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _variance_item_to_dict(self, item: ActivityVarianceItem) -> dict[str, Any]:
        return {
            "activity_id": item.activity_id,
            "project_id": item.project_id,
            "activity_code": item.activity_code,
            "name": item.name,
            "wbs_code": item.wbs_code,
            "discipline": item.discipline,
            "location": item.location,
            "planned_quantity": item.planned_quantity,
            "planned_unit": item.planned_unit,
            "planned_start_date": item.planned_start_date,
            "planned_finish_date": item.planned_finish_date,
            "actual_quantity_total": item.actual_quantity_total,
            "actual_unit": item.actual_unit,
            "latest_actual_date": item.latest_actual_date,
            "approved_actuals_count": item.approved_actuals_count,
            "quantity_variance": item.quantity_variance,
            "progress_percent": item.progress_percent,
            "date_variance_days": item.date_variance_days,
            "variance_status": item.variance_status.value if item.variance_status else None,
            "is_flagged": item.is_flagged,
            "flag_reason": item.flag_reason,
        }

    def _risk_item_to_dict(self, item: ActivityRiskAssessment) -> dict[str, Any]:
        return {
            "activity_id": item.activity_id,
            "project_id": item.project_id,
            "activity_code": item.activity_code,
            "name": item.name,
            "wbs_code": item.wbs_code,
            "discipline": item.discipline,
            "location": item.location,
            "severity": item.severity.value if item.severity else None,
            "risk_score": item.risk_score,
            "categories": [c.value for c in item.categories],
            "is_critical_path": item.is_critical_path,
            "total_float": item.total_float,
            "date_variance_days": item.date_variance_days,
            "direct_successors_count": item.direct_successors_count,
            "transitive_successors_count": item.transitive_successors_count,
            "critical_slippage_successors_count": item.critical_slippage_successors_count,
            "variance_status": item.variance_status.value if item.variance_status else None,
            "progress_percent": item.progress_percent,
            "is_completed": item.is_completed,
        }


# Singleton service instance
report_export_service = ReportExportService()
