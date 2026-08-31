"""
SiteSync AI — Phase 8.2 Variance Router Integration & Security Tests.
Comprehensive test suite verifying:
  - Authentication and RBAC (Viewer, Supervisor, Planner, Admin)
  - Multi-tenant boundary protection and cross-project IDOR prevention
  - Query parameter validation (limit, offset, dates, status)
  - Mathematical and aggregation fidelity through HTTP endpoints
  - WBS and Project rollups across homogeneous vs heterogeneous units
  - Deterministic pagination and stable sorting
  - Strict read-only boundary (405 on POST, PUT, PATCH, DELETE)
  - Error sanitization (no internal SQL, stack traces, or secrets)
  - Static Phase 9 boundary check
"""

from __future__ import annotations

import inspect
import time
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

# pyrefly: ignore [missing-import]
import jwt
# pyrefly: ignore [missing-import]
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.decision import ApprovedActualResponse
from app.schemas.schedule import ScheduleActivityCreate
from app.services.decision_service import decision_service
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
    decision_service.actual_repo.clear()

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
# 1. Authentication Tests (401)
# ==============================================================================

@pytest.mark.asyncio
async def test_1_unauthenticated_summary_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_2_unauthenticated_activities_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_3_unauthenticated_wbs_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/wbs")
        assert resp.status_code == 401


# ==============================================================================
# 2. RBAC Authorization Tests (Viewer, Supervisor, Planner, Admin)
# ==============================================================================

@pytest.mark.parametrize(
    "user_id, role_name",
    [
        (USER_VIEWER, "viewer"),
        (USER_SUPERVISOR, "supervisor"),
        (USER_PLANNER, "planner"),
        (USER_ADMIN, "admin"),
    ],
)
@pytest.mark.asyncio
async def test_4_all_roles_can_read_summary_activities_wbs(user_id: str, role_name: str):
    token = create_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Summary
        r_sum = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers)
        assert r_sum.status_code == 200, f"Role {role_name} failed summary with {r_sum.text}"

        # Activities
        r_act = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities", headers=headers)
        assert r_act.status_code == 200, f"Role {role_name} failed activities with {r_act.text}"

        # WBS
        r_wbs = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/wbs", headers=headers)
        assert r_wbs.status_code == 200, f"Role {role_name} failed wbs with {r_wbs.text}"


# ==============================================================================
# 3. Tenant Isolation / IDOR Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_5_cross_tenant_access_blocked():
    token_outsider = create_jwt(USER_OUTSIDER)
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Outsider attempts to read Project A summary
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers_outsider)
        assert r1.status_code == 403

        # Outsider attempts to read Project A activities
        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities", headers=headers_outsider)
        assert r2.status_code == 403

        # Outsider attempts to read Project A WBS
        r3 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/wbs", headers=headers_outsider)
        assert r3.status_code == 403


# ==============================================================================
# 4. Query Parameter Validations
# ==============================================================================

@pytest.mark.asyncio
async def test_6_query_parameter_validations():
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # limit < 1
        r = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?limit=0", headers=headers)
        assert r.status_code == 422

        # limit > 100
        r = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?limit=101", headers=headers)
        assert r.status_code == 422

        # offset < 0
        r = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?offset=-1", headers=headers)
        assert r.status_code == 422

        # invalid date range (from_date > to_date)
        r = await client.get(
            f"/api/v1/projects/{PROJECT_A}/variance/activities?from_date=2026-08-20&to_date=2026-08-10",
            headers=headers,
        )
        assert r.status_code == 400
        assert "INVALID_DATE_RANGE" in r.text

        # invalid variance_status
        r = await client.get(
            f"/api/v1/projects/{PROJECT_A}/variance/activities?variance_status=super_delayed",
            headers=headers,
        )
        assert r.status_code == 400
        assert "INVALID_VARIANCE_STATUS" in r.text


# ==============================================================================
# 5. Mathematical Correctness Through API
# ==============================================================================

@pytest.mark.asyncio
async def test_7_mathematical_correctness_through_api():
    # Activity 1: Planned 100 LF, Actual 80 LF (under plan -> -20 LF)
    act1 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-101",
            name="Piping Spools",
            planned_quantity=100.0,
            planned_unit="LF",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )

    # Activity 2: Planned 100 LF, Actual 120 LF (over plan -> +20 LF)
    act2 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-102",
            name="Underground Drainage",
            planned_quantity=100.0,
            planned_unit="LF",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )


    # Add approved actuals for Act 1: 30 LF on 8/5 + 50 LF on 8/8 = 80 LF total
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act1.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=30.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 5),
            source_evidence=["30 LF installed"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act1.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=1,
            actual_quantity=50.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 8),
            source_evidence=["50 LF installed"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # Add approved actuals for Act 2: 120 LF on 8/13 (3 days late)
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act2.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=120.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 13),
            source_evidence=["120 LF completed"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        items = body["items"]

        # Act 1 check
        item1 = next(i for i in items if i["activity_code"] == "ACT-101")
        assert item1["actual_quantity_total"] == 80.0
        assert item1["quantity_variance"] == -20.0
        assert item1["progress_percent"] == 80.0
        assert item1["approved_actuals_count"] == 2
        assert item1["latest_actual_date"] == "2026-08-08"
        assert item1["date_variance_days"] == -2  # 2 days early
        assert item1["variance_status"] == "in_progress"

        # Act 2 check
        item2 = next(i for i in items if i["activity_code"] == "ACT-102")
        assert item2["actual_quantity_total"] == 120.0
        assert item2["quantity_variance"] == 20.0
        assert item2["progress_percent"] == 120.0  # Over-delivered unclamped
        assert item2["date_variance_days"] == 3  # 3 days late
        assert item2["variance_status"] == "over_delivered"


# ==============================================================================
# 6. Unquantified and Unit Mismatch API Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_8_unquantified_and_unit_mismatch_through_api():
    # Milestone (unquantified)
    await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-M1",
            name="Foundation Inspection Milestone",
            planned_quantity=None,
            planned_unit=None,
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )

    # Actual unit mismatch: Planned in spools, actual reported in LF
    act_mismatch = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-M2",
            name="Pipe Spools Erection",
            planned_quantity=50.0,
            planned_unit="spools",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act_mismatch.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=50.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 9),
            source_evidence=["50 LF installed"],
            approved_by=UUID(USER_VIEWER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]

        m1 = next(i for i in items if i["activity_code"] == "ACT-M1")
        assert m1["variance_status"] == "unquantified"
        assert m1["planned_quantity"] is None
        assert m1["quantity_variance"] is None
        assert m1["progress_percent"] is None

        m2 = next(i for i in items if i["activity_code"] == "ACT-M2")
        assert m2["variance_status"] == "unit_mismatch"
        assert m2["quantity_variance"] is None
        assert m2["progress_percent"] is None


# ==============================================================================
# 7. Summary & WBS Rollups Tests (Homogeneous vs Heterogeneous)
# ==============================================================================

@pytest.mark.asyncio
async def test_9_wbs_and_project_rollups_through_api():
    # Activity A: WBS 1.2, 100 LF planned, 50 LF actual
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-A",
            name="Pipe A",
            wbs_code="1.2",
            planned_quantity=100.0,
            planned_unit="LF",
        ),
    )
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act_a.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=50.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 5),
            source_evidence=["50 LF"],
            approved_by=UUID(USER_VIEWER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # Activity B: WBS 1.2, 20 tons planned, 10 tons actual
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-B",
            name="Steel B",
            wbs_code="1.2",
            planned_quantity=20.0,
            planned_unit="tons",
        ),
    )

    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act_b.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=10.0,
            actual_unit="tons",
            actual_date=date(2026, 8, 5),
            source_evidence=["10 tons"],
            approved_by=UUID(USER_VIEWER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # WBS Rollup check
        r_wbs = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/wbs", headers=headers)
        assert r_wbs.status_code == 200
        wbs_body = r_wbs.json()
        assert wbs_body["total"] == 1
        wbs_12 = wbs_body["items"][0]
        assert wbs_12["wbs_code"] == "1.2"
        # Must have 2 distinct unit rollups (LF and tons), never 120 'units'!
        assert len(wbs_12["unit_rollups"]) == 2

        # Summary check
        r_sum = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers)
        assert r_sum.status_code == 200
        sum_body = r_sum.json()
        assert sum_body["total_activities"] == 2
        assert sum_body["activities_with_progress"] == 2
        assert sum_body["in_progress_activities"] == 2
        # Heterogeneous units in project -> overall_progress_percent MUST be None!
        assert sum_body["overall_progress_percent"] is None
        assert len(sum_body["unit_rollups"]) == 2


# ==============================================================================
# 8. Deterministic Pagination Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_10_pagination_stability_and_no_overlap():
    # Create 5 activities ACT-01 to ACT-05
    for i in range(1, 6):
        await schedule_service.create_or_update_activity(
            PROJECT_A,
            ScheduleActivityCreate(
                activity_code=f"ACT-{i:02d}",
                name=f"Task {i}",
                planned_quantity=100.0,
                planned_unit="LF",
            ),
        )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Page 1: limit 2, offset 0 -> ACT-01, ACT-02
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?limit=2&offset=0", headers=headers)
        assert r1.status_code == 200
        p1 = r1.json()
        assert p1["total"] == 5
        assert [i["activity_code"] for i in p1["items"]] == ["ACT-01", "ACT-02"]

        # Page 2: limit 2, offset 2 -> ACT-03, ACT-04
        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?limit=2&offset=2", headers=headers)
        assert r2.status_code == 200
        p2 = r2.json()
        assert [i["activity_code"] for i in p2["items"]] == ["ACT-03", "ACT-04"]

        # Page 3: limit 2, offset 4 -> ACT-05
        r3 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/activities?limit=2&offset=4", headers=headers)
        assert r3.status_code == 200
        p3 = r3.json()
        assert [i["activity_code"] for i in p3["items"]] == ["ACT-05"]


# ==============================================================================
# 9. Strict Read-Only Boundary (405 on Mutations)
# ==============================================================================

@pytest.mark.asyncio
async def test_11_mutations_disallowed_on_variance_endpoints():
    token = create_jwt(USER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST
        r = await client.post(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers, json={})
        assert r.status_code == 405

        # PUT
        r = await client.put(f"/api/v1/projects/{PROJECT_A}/variance/activities", headers=headers, json={})
        assert r.status_code == 405

        # PATCH
        r = await client.patch(f"/api/v1/projects/{PROJECT_A}/variance/wbs", headers=headers, json={})
        assert r.status_code == 405

        # DELETE
        r = await client.delete(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers)
        assert r.status_code == 405


# ==============================================================================
# 10. Error Sanitization & Static Phase 9 Boundary Check
# ==============================================================================

@pytest.mark.asyncio
async def test_12_error_sanitization_contains_no_secrets():
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid project ID format or non-existent
        r = await client.get("/api/v1/projects/non-existent-uuid/variance/summary", headers=headers)
        assert r.status_code == 404
        assert "traceback" not in r.text.lower()
        assert "postgres" not in r.text.lower()
        assert "secret" not in r.text.lower()


def test_13_phase9_boundary_static_check_on_router_and_query_service():
    """
    Verifies that Phase 8.2 router and query service contain zero Phase 9 concepts.
    """
    import app.api.v1.routers.variance as var_router
    import app.services.variance_query_service as var_query

    router_src = inspect.getsource(var_router)
    query_src = inspect.getsource(var_query)

    forbidden = [
        "critical_path",
        "delay_prediction",
        "delay_forecast",
        "forecasting",
        "risk_score",
        "risk_level",
        "risk_heatmap",
        "downstream_impact",
        "total_float",
        "free_float",
        "slack_days",
    ]

    for token in forbidden:
        assert token not in router_src.lower(), f"Forbidden Phase 9 token '{token}' in router"
        assert token not in query_src.lower(), f"Forbidden Phase 9 token '{token}' in query service"
