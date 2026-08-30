"""
SiteSync AI — Phase 3 Reports API & Authorization Tests.
Tests:
  - List reports in project
  - Get report by ID
  - Report creation with supervisor/planner/admin roles
  - Viewer role modification denial (403)
  - Admin deletion vs non-admin deletion denial (403)
  - Server-side IDOR / cross-project isolation (403)
  - Unauthenticated access rejection (401)
"""

from __future__ import annotations

import time
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
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

    # User memberships on proj-mtp
    membership_registry.add_membership("user-admin", "proj-mtp", ProjectRole.ADMIN)
    membership_registry.add_membership("user-planner", "proj-mtp", ProjectRole.PLANNER)
    membership_registry.add_membership("user-supervisor", "proj-mtp", ProjectRole.SUPERVISOR)
    membership_registry.add_membership("user-viewer", "proj-mtp", ProjectRole.VIEWER)

    # User outsider is only on proj-other
    membership_registry.add_membership("user-outsider", "proj-other", ProjectRole.ADMIN)

    # Seed a report in proj-mtp
    report_service.create_report(
        project_id="proj-mtp",
        data=type("Obj", (), {
            "name": "Initial Site Report",
            "file_name": "Site_Report.pdf",
            "file_type": "pdf",
            "file_size": 1024,
            "source": "manual_upload",
        })(),
        uploaded_by_id="user-supervisor",
    )

    yield


def test_unauthenticated_reports_list_returns_401():
    response = client.get("/api/v1/projects/proj-mtp/reports")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_viewer_can_list_reports():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["reports"][0]["name"] == "Initial Site Report"


def test_supervisor_can_create_report():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    payload = {
        "name": "Daily Piping Progress",
        "file_name": "Piping_Log_May18.xlsx",
        "file_type": "xlsx",
        "file_size": 204800,
        "source": "manual_upload",
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Daily Piping Progress"
    assert body["file_type"] == "xlsx"
    assert body["status"] == "uploaded"


def test_planner_can_create_report():
    token = create_test_jwt("user-planner", "planner@sitesync.ai")
    payload = {
        "name": "Civil Diary",
        "file_name": "Civil_Diary.pdf",
        "file_type": "pdf",
        "file_size": 512000,
        "source": "manual_upload",
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


def test_viewer_cannot_create_report_returns_403():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    payload = {
        "name": "Unauthorized Report",
        "file_name": "Test.pdf",
        "file_type": "pdf",
        "file_size": 100,
        "source": "manual_upload",
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_admin_can_delete_report():
    token = create_test_jwt("user-admin", "admin@sitesync.ai")
    reports_res = client.get(
        "/api/v1/projects/proj-mtp/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    report_id = reports_res.json()["reports"][0]["id"]

    del_res = client.delete(
        f"/api/v1/projects/proj-mtp/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


def test_planner_cannot_delete_report_returns_403():
    token = create_test_jwt("user-planner", "planner@sitesync.ai")
    reports_res = client.get(
        "/api/v1/projects/proj-mtp/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    report_id = reports_res.json()["reports"][0]["id"]

    del_res = client.delete(
        f"/api/v1/projects/proj-mtp/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_outsider_cannot_access_project_reports_returns_403_idor():
    token = create_test_jwt("user-outsider", "outsider@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
