"""
Field Event Domain Service.
Handles field event creation, retrieval, updates, and scoping to project boundary.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.schemas.events import (
    FieldEventCreate,
    FieldEventListResponse,
    FieldEventResponse,
    FieldEventStatus,
    FieldEventUpdate,
)
from app.services.report_service import report_service


class EventService:
    """In-memory & database abstraction service for construction field events."""

    def __init__(self) -> None:
        # key: event_id -> event_dict
        self._events: dict[str, dict[str, Any]] = {}

    def list_events(
        self, project_id: str, report_id: str | None = None
    ) -> FieldEventListResponse:
        """List all field events for a project with optional report_id filter."""
        events = [
            self._to_response(e)
            for e in self._events.values()
            if e["project_id"] == project_id
            and (report_id is None or e.get("report_id") == report_id)
        ]
        # Sort by event_date desc, created_at desc
        events.sort(key=lambda x: (x.event_date, x.created_at), reverse=True)
        return FieldEventListResponse(
            events=events,
            total=len(events),
        )

    def get_event(self, project_id: str, event_id: str) -> FieldEventResponse | None:
        """Get a single field event scoped to project."""
        event = self._events.get(event_id)
        if not event or event["project_id"] != project_id:
            return None
        return self._to_response(event)

    def create_event(
        self,
        project_id: str,
        data: FieldEventCreate,
        extracted_by_id: str,
    ) -> FieldEventResponse:
        """Create a new field event."""
        # If report_id is provided, verify it belongs to this project
        report_name = None
        if data.report_id:
            report = report_service.get_report(project_id, data.report_id)
            if report:
                report_name = report.name

        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        record = {
            "id": event_id,
            "project_id": project_id,
            "report_id": data.report_id,
            "report_name": report_name,
            "event_type": data.event_type,
            "description": data.description,
            "discipline": data.discipline,
            "location": data.location,
            "event_date": data.event_date,
            "progress_percent": float(data.progress_percent),
            "status": FieldEventStatus.PENDING,
            "extracted_by": extracted_by_id,
            "created_at": now,
            "updated_at": now,
        }
        self._events[event_id] = record
        return self._to_response(record)

    def update_event(
        self,
        project_id: str,
        event_id: str,
        data: FieldEventUpdate,
    ) -> FieldEventResponse | None:
        """Update an existing field event."""
        event = self._events.get(event_id)
        if not event or event["project_id"] != project_id:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if value is not None:
                event[key] = value

        event["updated_at"] = datetime.now(timezone.utc)
        return self._to_response(event)

    def delete_event(self, project_id: str, event_id: str) -> bool:
        """Delete an event if it belongs to project."""
        event = self._events.get(event_id)
        if not event or event["project_id"] != project_id:
            return False
        del self._events[event_id]
        return True

    def _to_response(self, e: dict[str, Any]) -> FieldEventResponse:
        report_name = e.get("report_name")
        if not report_name and e.get("report_id"):
            rep = report_service.get_report(e["project_id"], e["report_id"])
            if rep:
                report_name = rep.name

        return FieldEventResponse(
            id=e["id"],
            project_id=e["project_id"],
            report_id=e.get("report_id"),
            report_name=report_name,
            event_type=e["event_type"],
            description=e["description"],
            discipline=e["discipline"],
            location=e["location"],
            event_date=e["event_date"],
            progress_percent=float(e["progress_percent"]),
            status=e["status"],
            extracted_by=e.get("extracted_by"),
            created_at=e["created_at"],
            updated_at=e["updated_at"],
        )

    def clear(self) -> None:
        self._events.clear()

    def seed_demo_data(self) -> None:
        """Seed deterministic demo events for MTP Refinery Expansion."""
        now = datetime.now(timezone.utc)
        demo_events = [
            {
                "id": "evt-demo-001",
                "project_id": "proj-mtp-001",
                "report_id": "rep-demo-001",
                "report_name": "Daily Progress Report — 18 May",
                "event_type": "Spool Erection",
                "description": "Spool erection completed on Line 24 in Rack 3 Area",
                "discipline": "Piping",
                "location": "Unit-1 / Piping Area",
                "event_date": date(2025, 5, 18),
                "progress_percent": 100.0,
                "status": FieldEventStatus.PENDING,
                "extracted_by": "user-supervisor-01",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "evt-demo-002",
                "project_id": "proj-mtp-001",
                "report_id": "rep-demo-001",
                "report_name": "Daily Progress Report — 18 May",
                "event_type": "Foundation Excavation",
                "description": "Excavation completed for T-101 equipment foundation",
                "discipline": "Civil",
                "location": "Storage Tank Area / Foundation T-101",
                "event_date": date(2025, 5, 18),
                "progress_percent": 100.0,
                "status": FieldEventStatus.PENDING,
                "extracted_by": "user-supervisor-01",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "evt-demo-003",
                "project_id": "proj-mtp-001",
                "report_id": "rep-demo-002",
                "report_name": "Site Diary & Quantity Log — 17 May",
                "event_type": "Cable Pulling",
                "description": "Cable pulling in progress Building 3 tray routing",
                "discipline": "Electrical",
                "location": "Substation 3 / Cable Tray B",
                "event_date": date(2025, 5, 17),
                "progress_percent": 65.0,
                "status": FieldEventStatus.PENDING,
                "extracted_by": "user-planner-01",
                "created_at": now,
                "updated_at": now,
            },
        ]
        for evt in demo_events:
            self._events[evt["id"]] = evt


event_service = EventService()
event_service.seed_demo_data()
