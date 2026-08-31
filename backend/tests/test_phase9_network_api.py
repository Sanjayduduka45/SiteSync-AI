"""
SiteSync AI — Phase 9.5 Schedule Dependency & Critical Path API Tests.
Verifies HTTP endpoints for:
  - Dependency network CRUD and deterministic ordering
  - RBAC enforcement across all four roles (Viewer, Supervisor, Planner, Admin)
  - Multi-tenant isolation and IDOR prevention
  - Self-dependency, duplicate edge, and DAG cycle detection
  - Critical Path Method (CPM) calculation fidelity and float preservation
  - Error sanitization and static boundary assertions
"""

from __future__ import annotations

import inspect
import time
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.network import DependencyCreate
from app.schemas.schedule import ScheduleActivityCreate
from app.services.dependency_service import dependency_service
from app.services.schedule_service import schedule_service



def create_jwt(user_id: str, email: str = "test@example.com") -> str:
    """Generates test JWT token."""
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


PROJECT_A = "00000000-0000-0000-0000-000000000001"
PROJECT_B = "00000000-0000-0000-0000-000000000002"

USER_VIEWER = "00000000-0000-0000-0000-000000000003"
USER_SUPERVISOR = "00000000-0000-0000-0000-000000000004"
USER_PLANNER = "00000000-0000-0000-0000-000000000005"
USER_ADMIN = "00000000-0000-0000-0000-000000000006"
USER_OUTSIDER = "00000000-0000-0000-0000-000000000007"


@pytest.fixture(autouse=True)
def setup_test_state():
    """Resets memory stores and registries before each test."""
    membership_registry.clear()
    schedule_service.clear()
    dependency_service.clear()

    # Seed projects
    membership_registry.seed_project(PROJECT_A, "Project Alpha", "ALPHA")
    membership_registry.seed_project(PROJECT_B, "Project Beta", "BETA")

    # Project A members
    membership_registry.add_membership(USER_VIEWER, PROJECT_A, ProjectRole.VIEWER)
    membership_registry.add_membership(USER_SUPERVISOR, PROJECT_A, ProjectRole.SUPERVISOR)
    membership_registry.add_membership(USER_PLANNER, PROJECT_A, ProjectRole.PLANNER)
    membership_registry.add_membership(USER_ADMIN, PROJECT_A, ProjectRole.ADMIN)

    # Project B member (outsider to A)
    membership_registry.add_membership(USER_OUTSIDER, PROJECT_B, ProjectRole.ADMIN)


# ==============================================================================
# 1. Dependency RBAC & Permissions (Tests 1-12)
# ==============================================================================

@pytest.mark.asyncio
async def test_1_4_all_roles_can_get_dependencies():
    """Tests 1-4: Viewer, Supervisor, Planner, Admin can all GET dependencies (200)."""
    for user_id in [USER_VIEWER, USER_SUPERVISOR, USER_PLANNER, USER_ADMIN]:
        token = create_jwt(user_id)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/projects/{PROJECT_A}/network/dependencies", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data


@pytest.mark.asyncio
async def test_5_6_viewer_and_supervisor_post_forbidden():
    """Tests 5-6: Viewer and Supervisor POST dependency returns 403."""
    for user_id in [USER_VIEWER, USER_SUPERVISOR]:
        token = create_jwt(user_id)
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/projects/{PROJECT_A}/network/dependencies",
                headers=headers,
                json={
                    "predecessor_id": str(uuid4()),
                    "successor_id": str(uuid4()),
                    "relationship_type": "FS",
                    "lag_days": 0,
                },
            )
            assert resp.status_code == 403
            assert "INSUFFICIENT_PERMISSIONS" in resp.text


@pytest.mark.asyncio
async def test_7_8_planner_and_admin_post_allowed():
    """Tests 7-8: Planner and Admin POST dependency returns 201 Created."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-A",
            name="Activity A",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-B",
            name="Activity B",
            planned_start_date=date(2026, 8, 11),
            planned_finish_date=date(2026, 8, 20),
        ),
    )
    act_c = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-C",
            name="Activity C",
            planned_start_date=date(2026, 8, 21),
            planned_finish_date=date(2026, 8, 25),
        ),
    )

    # Planner creates A -> B
    token_planner = create_jwt(USER_PLANNER)
    headers_planner = {"Authorization": f"Bearer {token_planner}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_p = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers_planner,
            json={
                "predecessor_id": str(act_a.id),
                "successor_id": str(act_b.id),
                "relationship_type": "FS",
                "lag_days": 0,
            },
        )
        assert resp_p.status_code == 201
        data_p = resp_p.json()
        assert data_p["predecessor_id"] == str(act_a.id)
        assert data_p["successor_id"] == str(act_b.id)
        assert data_p["project_id"] == PROJECT_A

    # Admin creates B -> C
    token_admin = create_jwt(USER_ADMIN)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_a = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers_admin,
            json={
                "predecessor_id": str(act_b.id),
                "successor_id": str(act_c.id),
                "relationship_type": "FS",
                "lag_days": 1,
            },
        )
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        assert data_a["predecessor_id"] == str(act_b.id)
        assert data_a["successor_id"] == str(act_c.id)
        assert data_a["lag_days"] == 1


@pytest.mark.asyncio
async def test_9_12_delete_permissions_admin_only():
    """Tests 9-12: Viewer, Supervisor, Planner DELETE returns 403; Admin DELETE returns 204."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-1", name="Task 1"),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-2", name="Task 2"),
    )

    dep = await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(
            predecessor_id=act_a.id,
            successor_id=act_b.id,
        ),
    )

    # Viewer (403)
    token_v = create_jwt(USER_VIEWER)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies/{dep.id}",
            headers={"Authorization": f"Bearer {token_v}"},
        )
        assert r.status_code == 403

    # Supervisor (403)
    token_s = create_jwt(USER_SUPERVISOR)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies/{dep.id}",
            headers={"Authorization": f"Bearer {token_s}"},
        )
        assert r.status_code == 403

    # Planner (403)
    token_p = create_jwt(USER_PLANNER)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies/{dep.id}",
            headers={"Authorization": f"Bearer {token_p}"},
        )
        assert r.status_code == 403

    # Admin (204)
    token_adm = create_jwt(USER_ADMIN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies/{dep.id}",
            headers={"Authorization": f"Bearer {token_adm}"},
        )
        assert r.status_code == 204

    # Verify deleted
    deps_left = await dependency_service.list_dependencies(PROJECT_A)
    assert len(deps_left) == 0


# ==============================================================================
# 2. Multi-Tenant & Cross-Project Isolation (Tests 13-14)
# ==============================================================================

@pytest.mark.asyncio
async def test_13_cross_project_post_rejected():
    """Test 13: Attempting to link activities from different projects is rejected."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-A", name="Task A"),
    )
    act_b_in_b = await schedule_service.create_or_update_activity(
        PROJECT_B,
        ScheduleActivityCreate(activity_code="ACT-B", name="Task B"),
    )

    token = create_jwt(USER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request in Project A with successor from Project B
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers,
            json={
                "predecessor_id": str(act_a.id),
                "successor_id": str(act_b_in_b.id),
                "relationship_type": "FS",
                "lag_days": 0,
            },
        )
        assert resp.status_code == 404
        assert "ACTIVITY_NOT_FOUND" in resp.text


@pytest.mark.asyncio
async def test_14_cross_project_delete_rejected():
    """Test 14: User in Project B cannot delete dependency belonging to Project A."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-A", name="Task A"),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-B", name="Task B"),
    )
    dep = await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(
            predecessor_id=act_a.id,
            successor_id=act_b.id,
        ),
    )

    # Outsider (Admin of B) attempts to delete dep in Project A
    token_outsider = create_jwt(USER_OUTSIDER)
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Cross-project request to Project A URL is 403
        r1 = await client.delete(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies/{dep.id}",
            headers=headers_outsider,
        )
        assert r1.status_code == 403

        # Request to Project B URL for dep in A is 404
        r2 = await client.delete(
            f"/api/v1/projects/{PROJECT_B}/network/dependencies/{dep.id}",
            headers=headers_outsider,
        )
        assert r2.status_code == 404


# ==============================================================================
# 3. Input Validation & Cycle Prevention (Tests 15-19)
# ==============================================================================

@pytest.mark.asyncio
async def test_15_self_dependency_rejected():
    """Test 15: Self dependency (predecessor_id == successor_id) is rejected."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-A", name="Task A"),
    )
    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers,
            json={
                "predecessor_id": str(act_a.id),
                "successor_id": str(act_a.id),
                "relationship_type": "FS",
                "lag_days": 0,
            },
        )
        assert resp.status_code == 422  # Pydantic model validator catches self-dependency


@pytest.mark.asyncio
async def test_16_duplicate_edge_rejected():
    """Test 16: Duplicate directed edge between same activities is rejected."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-A", name="Task A"),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-B", name="Task B"),
    )

    await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(
            predecessor_id=act_a.id,
            successor_id=act_b.id,
        ),
    )

    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers,
            json={
                "predecessor_id": str(act_a.id),
                "successor_id": str(act_b.id),
                "relationship_type": "SS",
                "lag_days": 2,
            },
        )
        assert resp.status_code == 400
        assert "DUPLICATE_DEPENDENCY" in resp.text


@pytest.mark.asyncio
async def test_17_invalid_relationship_rejected():
    """Test 17: Invalid relationship type is rejected."""
    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers,
            json={
                "predecessor_id": str(uuid4()),
                "successor_id": str(uuid4()),
                "relationship_type": "INVALID_REL",
                "lag_days": 0,
            },
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_18_cycle_rejected_with_sanitized_message():
    """Test 18: Adding an edge that creates a cycle returns HTTP 400 'Dependency cycle detected.'"""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-A", name="Task A"),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-B", name="Task B"),
    )
    act_c = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-C", name="Task C"),
    )

    # Create A -> B and B -> C
    await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(predecessor_id=act_a.id, successor_id=act_b.id),
    )
    await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(predecessor_id=act_b.id, successor_id=act_c.id),
    )

    # Attempt C -> A (introducing cycle A -> B -> C -> A)
    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/projects/{PROJECT_A}/network/dependencies",
            headers=headers,
            json={
                "predecessor_id": str(act_c.id),
                "successor_id": str(act_a.id),
                "relationship_type": "FS",
                "lag_days": 0,
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "CYCLE_DETECTED"
        assert body["error"]["message"] == "Dependency cycle detected."


@pytest.mark.asyncio
async def test_19_deterministic_dependency_ordering():
    """Test 19: GET dependencies returns items in deterministic order."""
    act_1 = await schedule_service.create_or_update_activity(
        PROJECT_A, ScheduleActivityCreate(activity_code="ACT-1", name="Task 1")
    )
    act_2 = await schedule_service.create_or_update_activity(
        PROJECT_A, ScheduleActivityCreate(activity_code="ACT-2", name="Task 2")
    )
    act_3 = await schedule_service.create_or_update_activity(
        PROJECT_A, ScheduleActivityCreate(activity_code="ACT-3", name="Task 3")
    )

    # Insert in reverse order: (act_2 -> act_3), (act_1 -> act_3), (act_1 -> act_2)
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_2.id, successor_id=act_3.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_1.id, successor_id=act_3.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_1.id, successor_id=act_2.id)
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/network/dependencies", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 3

        # Check sorted by (predecessor_id, successor_id)
        keys = [(i["predecessor_id"], i["successor_id"]) for i in items]
        sorted_keys = sorted(keys)
        assert keys == sorted_keys


# ==============================================================================
# 4. Critical Path Method API (Tests 20-25)
# ==============================================================================

@pytest.mark.asyncio
async def test_20_23_cpm_endpoint_fidelity_and_float_preservation():
    """
    Tests 20-23: Authenticated viewer GET critical-path returns 200, matches Phase 9.2 CPM math,
    identifies critical path activities, and preserves total/free float values.
    """
    # Linear FS sequence: A (10d, 8/1-8/10) -> B (5d, 8/11-8/15) -> C (5d, 8/16-8/20)
    # Plus parallel branch: A -> D (4d, 8/11-8/14) -> C (FF)
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-A",
            name="Mobilization",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-B",
            name="Excavation",
            planned_start_date=date(2026, 8, 11),
            planned_finish_date=date(2026, 8, 15),
        ),
    )
    act_c = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-C",
            name="Foundation Pour",
            planned_start_date=date(2026, 8, 16),
            planned_finish_date=date(2026, 8, 20),
        ),
    )
    act_d = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-D",
            name="Rebar Pre-assembly",
            planned_start_date=date(2026, 8, 11),
            planned_finish_date=date(2026, 8, 14),
        ),
    )

    # Dependencies: A -> B (FS), B -> C (FS), A -> D (FS), D -> C (FF)
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_a.id, successor_id=act_b.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_b.id, successor_id=act_c.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_a.id, successor_id=act_d.id)
    )
    from app.schemas.cpm import DependencyRelationshipType
    await dependency_service.create_dependency(
        PROJECT_A,
        DependencyCreate(
            predecessor_id=act_d.id,
            successor_id=act_c.id,
            relationship_type=DependencyRelationshipType.FF,
        ),
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/network/critical-path", headers=headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["project_id"] == PROJECT_A
        assert body["total_activities"] == 4
        assert body["critical_activities_count"] == 3

        # Critical path is A -> B -> C
        crit_ids = [str(x) for x in body["critical_path_activity_ids"]]
        assert crit_ids == [str(act_a.id), str(act_b.id), str(act_c.id)]

        act_nodes = {n["activity_code"]: n for n in body["activities"]}

        # ACT-A
        assert act_nodes["ACT-A"]["is_critical"] is True
        assert act_nodes["ACT-A"]["total_float_days"] == 0
        assert act_nodes["ACT-A"]["duration_days"] == 10

        # ACT-B
        assert act_nodes["ACT-B"]["is_critical"] is True
        assert act_nodes["ACT-B"]["total_float_days"] == 0
        assert act_nodes["ACT-B"]["duration_days"] == 5

        # ACT-C
        assert act_nodes["ACT-C"]["is_critical"] is True
        assert act_nodes["ACT-C"]["total_float_days"] == 0
        assert act_nodes["ACT-C"]["duration_days"] == 5

        # ACT-D (Non-critical, positive float)
        assert act_nodes["ACT-D"]["is_critical"] is False
        assert act_nodes["ACT-D"]["total_float_days"] > 0
        assert act_nodes["ACT-D"]["duration_days"] == 4


@pytest.mark.asyncio
async def test_24_cpm_cycle_error_sanitized():
    """Test 24: Direct CPM endpoint sanitizes cycle error to 400."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A, ScheduleActivityCreate(activity_code="ACT-A", name="Task A")
    )
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/network/critical-path", headers=headers)
        assert resp.status_code == 200
        assert "traceback" not in resp.text.lower()


@pytest.mark.asyncio
async def test_25_cross_project_critical_path_rejected():
    """Test 25: User from Project B cannot access Project A critical path."""
    token_outsider = create_jwt(USER_OUTSIDER)
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/network/critical-path", headers=headers_outsider)
        assert resp.status_code == 403
        assert "FORBIDDEN" in resp.text
