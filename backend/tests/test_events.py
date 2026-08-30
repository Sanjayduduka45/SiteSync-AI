"""
SiteSync AI — Phase 3 Field Events API & Authorization Tests.
Tests:
  - List field events in project
  - Filter events by report_id
  - Get event by ID
  - Event creation with supervisor/planner/admin roles
  - Event patching with planner/admin roles
  - Supervisor patch denial (403)
  - Viewer modification denial (403)
  - Data validation (progress 0..100)
  - Cross-project isolation (403)
"""

from __future__ import annotations

import time
import jwt
import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.events import FieldEventCreate
from app.services.event_service import event_service
from app.services.report_service import report_service

client = TestClient(app)


def create_test_jwt(user_id: str, email: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_test_state():
    membership_registry.clear()
    report_service.clear()
    event_service.clear()

    # Projects
    membership_registry.seed_project(
        project_id="proj-mtp",
        name="MTP – Refinery Expansion",
        code="MTP-2026",
    )
    membership_registry.seed_project(
        project_id="proj-other",
        name="Other Project",
        code="OTH-2026",
    )

    # User memberships
    membership_registry.add_membership("user-admin", "proj-mtp", ProjectRole.ADMIN)
    membership_registry.add_membership("user-planner", "proj-mtp", ProjectRole.PLANNER)
    membership_registry.add_membership("user-supervisor", "proj-mtp", ProjectRole.SUPERVISOR)
    membership_registry.add_membership("user-viewer", "proj-mtp", ProjectRole.VIEWER)
    membership_registry.add_membership("user-outsider", "proj-other", ProjectRole.ADMIN)

    # Seed event
    event_service.create_event(
        project_id="proj-mtp",
        data=FieldEventCreate(
            event_type="Spool Erection",
            description="Spool erection completed on Line 24",
            discipline="Piping",
            location="Unit-1 / Piping Area",
            event_date=date(2025, 5, 18),
            progress_percent=100.0,
        ),
        extracted_by_id="user-supervisor",
    )

    yield


def test_viewer_can_list_events():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["events"][0]["event_type"] == "Spool Erection"


def test_supervisor_can_create_event():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    payload = {
        "event_type": "Concrete Pour",
        "description": "Foundation pad poured for compressor C-201",
        "discipline": "Civil",
        "location": "Compressor House / Pad C-201",
        "event_date": "2025-05-19",
        "progress_percent": 100.0,
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["event_type"] == "Concrete Pour"
    assert body["progress_percent"] == 100.0
    assert body["status"] == "pending"


def test_viewer_cannot_create_event_returns_403():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    payload = {
        "event_type": "Unauthorized Event",
        "description": "Should fail",
        "discipline": "Electrical",
        "location": "Substation",
        "event_date": "2025-05-19",
        "progress_percent": 50.0,
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_planner_can_patch_event():
    token = create_test_jwt("user-planner", "planner@sitesync.ai")
    events_res = client.get(
        "/api/v1/projects/proj-mtp/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    event_id = events_res.json()["events"][0]["id"]

    patch_res = client.patch(
        f"/api/v1/projects/proj-mtp/events/{event_id}",
        json={"progress_percent": 90.0, "status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    body = patch_res.json()
    assert body["progress_percent"] == 90.0
    assert body["status"] == "approved"


def test_supervisor_cannot_patch_event_returns_403():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    events_res = client.get(
        "/api/v1/projects/proj-mtp/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    event_id = events_res.json()["events"][0]["id"]

    patch_res = client.patch(
        f"/api/v1/projects/proj-mtp/events/{event_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_progress_percent_out_of_bounds_returns_422():
    token = create_test_jwt("user-planner", "planner@sitesync.ai")
    payload = {
        "event_type": "Invalid Event",
        "description": "Invalid progress",
        "discipline": "Piping",
        "location": "Unit-1",
        "event_date": "2025-05-19",
        "progress_percent": 150.0,  # Invalid: > 100
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_outsider_cannot_access_project_events_returns_403_idor():
    token = create_test_jwt("user-outsider", "outsider@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
