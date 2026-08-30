"""
Report Domain Service.
Handles report creation, listing, retrieval, and deletion scoped to project boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.reports import (
    ReportCreate,
    ReportListResponse,
    ReportResponse,
    ReportStatus,
)


class ReportService:
    """In-memory & database abstraction service for project reports."""

    def __init__(self) -> None:
        # key: report_id -> report_dict
        self._reports: dict[str, dict[str, Any]] = {}

    def list_reports(self, project_id: str) -> ReportListResponse:
        """List all reports for a specific project."""
        project_reports = [
            self._to_response(r)
            for r in self._reports.values()
            if r["project_id"] == project_id
        ]
        # Sort newest first
        project_reports.sort(key=lambda x: x.uploaded_at, reverse=True)
        return ReportListResponse(
            reports=project_reports,
            total=len(project_reports),
        )

    def get_report(self, project_id: str, report_id: str) -> ReportResponse | None:
        """Get a single report ensuring project ownership."""
        report = self._reports.get(report_id)
        if not report or report["project_id"] != project_id:
            return None
        return self._to_response(report)

    def create_report(
        self,
        project_id: str,
        data: ReportCreate,
        uploaded_by_id: str,
        uploaded_by_email: str | None = None,
    ) -> ReportResponse:
        """Create a new report record."""
        now = datetime.now(timezone.utc)
        report_id = str(uuid.uuid4())

        record = {
            "id": report_id,
            "project_id": project_id,
            "name": data.name,
            "file_name": data.file_name,
            "file_type": data.file_type.lower(),
            "file_size": data.file_size,
            "source": data.source,
            "status": ReportStatus.UPLOADED,
            "uploaded_by": uploaded_by_id,
            "uploaded_by_email": uploaded_by_email,
            "uploaded_at": now,
            "processed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self._reports[report_id] = record
        return self._to_response(record)

    def delete_report(self, project_id: str, report_id: str) -> bool:
        """Delete a report if it belongs to project."""
        report = self._reports.get(report_id)
        if not report or report["project_id"] != project_id:
            return False
        del self._reports[report_id]
        return True

    def _to_response(self, r: dict[str, Any]) -> ReportResponse:
        return ReportResponse(
            id=r["id"],
            project_id=r["project_id"],
            name=r["name"],
            file_name=r["file_name"],
            file_type=r["file_type"],
            file_size=r["file_size"],
            source=r["source"],
            status=r["status"],
            uploaded_by=r.get("uploaded_by"),
            uploaded_by_email=r.get("uploaded_by_email"),
            uploaded_at=r["uploaded_at"],
            processed_at=r.get("processed_at"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def clear(self) -> None:
        self._reports.clear()

    def seed_demo_data(self) -> None:
        """Seed deterministic demo data for MTP Refinery Expansion project."""
        now = datetime.now(timezone.utc)
        demo_reports = [
            {
                "id": "rep-demo-001",
                "project_id": "proj-mtp-001",
                "name": "Daily Progress Report — 18 May",
                "file_name": "Daily_Report_18_May.pdf",
                "file_type": "pdf",
                "file_size": 2_450_000,
                "source": "manual_upload",
                "status": ReportStatus.UPLOADED,
                "uploaded_by": "user-supervisor-01",
                "uploaded_by_email": "supervisor@sitesync.ai",
                "uploaded_at": now,
                "processed_at": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "rep-demo-002",
                "project_id": "proj-mtp-001",
                "name": "Site Diary & Quantity Log — 17 May",
                "file_name": "Site_Diary_17_May.xlsx",
                "file_type": "xlsx",
                "file_size": 1_120_000,
                "source": "manual_upload",
                "status": ReportStatus.UPLOADED,
                "uploaded_by": "user-planner-01",
                "uploaded_by_email": "planner@sitesync.ai",
                "uploaded_at": now,
                "processed_at": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
        for rep in demo_reports:
            self._reports[rep["id"]] = rep


report_service = ReportService()
report_service.seed_demo_data()
