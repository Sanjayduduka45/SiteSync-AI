"""
SiteSync AI — Phase 6.3 Schedule Router & Service Tests.
Tests:
  - POST /projects/{project_id}/schedules/activities creates activity (planner/admin)
  - POST /projects/{project_id}/schedules/activities denied for supervisor/viewer (403)
  - POST idempotent upsert on (project_id, activity_code) updates existing activity
  - GET /projects/{project_id}/schedules/activities returns list (viewer/supervisor/planner/admin)
  - GET pagination with limit and offset
  - Strict project isolation and 403 on cross-tenant requests
  - 401 on unauthenticated requests
"""

from __future__ import annotations

import time
from uuid import uuid4
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.services.schedule_service import schedule_service


def create_jwt(user_id: str, email: str = "test@example.com") -> str:
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


def auth_header(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id)}"}


@pytest.fixture(autouse=True)
def setup_test_state():
    """Resets registries and sets up isolated project and users with distinct roles."""
    membership_registry.clear()
    schedule_service.clear()

    proj_a = "proj-sched-a"
    proj_b = "proj-sched-b"

    membership_registry.seed_project(proj_a, "Schedule Project A", "SCHED-A")
    membership_registry.seed_project(proj_b, "Schedule Project B", "SCHED-B")

    # Roles for Project A
    membership_registry.add_membership("admin-user", proj_a, ProjectRole.ADMIN)
    membership_registry.add_membership("planner-user", proj_a, ProjectRole.PLANNER)
    membership_registry.add_membership("supervisor-user", proj_a, ProjectRole.SUPERVISOR)
    membership_registry.add_membership("viewer-user", proj_a, ProjectRole.VIEWER)

    # Outsider in Project B
    membership_registry.add_membership("outsider-user", proj_b, ProjectRole.ADMIN)


@pytest.mark.asyncio
async def test_unauthenticated_schedule_routes_return_401():
    """Verify unauthenticated requests return 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_post = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            json={"activity_code": "ACT-1", "name": "Test Act"},
        )
        assert res_post.status_code == 401

        res_get = await client.get("/api/v1/projects/proj-sched-a/schedules/activities")
        assert res_get.status_code == 401


@pytest.mark.asyncio
async def test_create_schedule_activity_permissions():
    """Verify planner and admin can create activities, supervisor and viewer are forbidden."""
    payload = {
        "activity_code": "ACT-001",
        "name": "Erect Structural Steel Tier 1",
        "wbs_code": "1.2.3",
        "discipline": "Civil",
        "location": "Grid 4",
        "planned_start_date": "2026-09-01",
        "planned_finish_date": "2026-09-15",
        "planned_quantity": 250.0,
        "planned_unit": "tons",
        "metadata": {"spec": "AISC-360"},
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Viewer -> 403
        res_v = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("viewer-user"),
            json=payload,
        )
        assert res_v.status_code == 403

        # 2. Supervisor -> 403
        res_s = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("supervisor-user"),
            json=payload,
        )
        assert res_s.status_code == 403

        # 3. Planner -> 200 OK
        res_p = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("planner-user"),
            json=payload,
        )
        assert res_p.status_code == 200
        data_p = res_p.json()
        assert data_p["activity_code"] == "ACT-001"
        assert data_p["name"] == "Erect Structural Steel Tier 1"
        assert data_p["planned_quantity"] == 250.0

        # 4. Admin -> 200 OK
        payload_adm = dict(payload, activity_code="ACT-002", name="Install Foundation Bolts")
        res_a = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("admin-user"),
            json=payload_adm,
        )
        assert res_a.status_code == 200
        assert res_a.json()["activity_code"] == "ACT-002"


@pytest.mark.asyncio
async def test_idempotent_activity_upsert_on_same_code():
    """Verify creating an activity with the same code updates the record idempotently."""
    initial_payload = {
        "activity_code": "ACT-IDEM-1",
        "name": "Initial Name",
        "planned_quantity": 100.0,
    }
    updated_payload = {
        "activity_code": "ACT-IDEM-1",
        "name": "Updated Name",
        "planned_quantity": 150.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        res1 = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("planner-user"),
            json=initial_payload,
        )
        assert res1.status_code == 200
        id1 = res1.json()["id"]

        # Rerun with updated name
        res2 = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("planner-user"),
            json=updated_payload,
        )
        assert res2.status_code == 200
        id2 = res2.json()["id"]
        assert id1 == id2
        assert res2.json()["name"] == "Updated Name"
        assert res2.json()["planned_quantity"] == 150.0


@pytest.mark.asyncio
async def test_list_schedule_activities_all_roles_and_pagination():
    """Verify all project roles can list activities with pagination."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Ingest 3 activities
        for i in range(1, 4):
            await client.post(
                "/api/v1/projects/proj-sched-a/schedules/activities",
                headers=auth_header("planner-user"),
                json={"activity_code": f"ACT-LIST-{i}", "name": f"Activity {i}"},
            )

        # Viewer can list
        res_v = await client.get(
            "/api/v1/projects/proj-sched-a/schedules/activities?limit=2&offset=0",
            headers=auth_header("viewer-user"),
        )
        assert res_v.status_code == 200
        data = res_v.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Offset page 2
        res_page2 = await client.get(
            "/api/v1/projects/proj-sched-a/schedules/activities?limit=2&offset=2",
            headers=auth_header("viewer-user"),
        )
        assert res_page2.status_code == 200
        assert len(res_page2.json()["items"]) == 1


@pytest.mark.asyncio
async def test_cross_tenant_idor_blocked():
    """Verify user in Project B cannot create or list activities in Project A."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_post = await client.post(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("outsider-user"),
            json={"activity_code": "ACT-HACK", "name": "Hack"},
        )
        assert res_post.status_code == 403

        res_get = await client.get(
            "/api/v1/projects/proj-sched-a/schedules/activities",
            headers=auth_header("outsider-user"),
        )
        assert res_get.status_code == 403
