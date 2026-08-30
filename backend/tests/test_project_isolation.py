"""
SiteSync AI — Phase 3 Project Isolation & Cross-Tenant Boundary Tests.
Validates that:
  - User A in Project A cannot read or modify Project B reports.
  - User A in Project A cannot read or modify Project B field events.
  - Role checks are evaluated strictly against the target project's membership.
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
def setup_two_projects():
    membership_registry.clear()
    report_service.clear()
    event_service.clear()

    # Seed Project A and Project B
    membership_registry.seed_project("proj-a", "Project Alpha", "ALPHA-01")
    membership_registry.seed_project("proj-b", "Project Beta", "BETA-02")

    # User A is Admin on Project A only
    membership_registry.add_membership("user-a", "proj-a", ProjectRole.ADMIN)

    # User B is Admin on Project B only
    membership_registry.add_membership("user-b", "proj-b", ProjectRole.ADMIN)

    # Seed report and event in Project A
    report_service.create_report(
        project_id="proj-a",
        data=type("Obj", (), {
            "name": "Alpha Daily Report",
            "file_name": "Alpha.pdf",
            "file_type": "pdf",
            "file_size": 100,
            "source": "manual_upload",
        })(),
        uploaded_by_id="user-a",
    )
    event_service.create_event(
        project_id="proj-a",
        data=FieldEventCreate(
            event_type="Civil Foundation",
            description="Alpha Foundation Work",
            discipline="Civil",
            location="Zone A",
            event_date=date(2025, 5, 18),
            progress_percent=50.0,
        ),
        extracted_by_id="user-a",
    )

    yield


def test_user_a_cannot_read_project_b_reports():
    token = create_test_jwt("user-a", "user_a@example.com")
    res = client.get(
        "/api/v1/projects/proj-b/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_user_a_cannot_create_report_in_project_b():
    token = create_test_jwt("user-a", "user_a@example.com")
    res = client.post(
        "/api/v1/projects/proj-b/reports",
        json={
            "name": "Malicious Report in Beta",
            "file_name": "Hack.pdf",
            "file_type": "pdf",
            "file_size": 100,
            "source": "manual_upload",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_user_b_cannot_read_project_a_events():
    token = create_test_jwt("user-b", "user_b@example.com")
    res = client.get(
        "/api/v1/projects/proj-a/events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_user_b_cannot_create_event_in_project_a():
    token = create_test_jwt("user-b", "user_b@example.com")
    res = client.post(
        "/api/v1/projects/proj-a/events",
        json={
            "event_type": "Hack Event",
            "description": "Cross project inject",
            "discipline": "Civil",
            "location": "Zone A",
            "event_date": "2025-05-18",
            "progress_percent": 10.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
