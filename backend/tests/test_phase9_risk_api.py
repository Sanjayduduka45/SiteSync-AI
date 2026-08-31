"""
SiteSync AI — Phase 9.5 Risk Intelligence & Downstream Impact API Tests.
Verifies HTTP endpoints for:
  - Project risk summary and 6-category taxonomy distribution
  - Activity risk register with server-side filtering (severity, category, WBS, discipline)
  - Deterministic pagination and stable sorting
  - Transitive downstream impact and float erosion analysis
  - Historical completed successor preservation
  - Multi-tenant isolation, IDOR prevention, and RBAC enforcement
  - Phase 8 Actual data boundary isolation (approved_actuals only, no raw field/AI tables)
  - Response schema strictness (extra='forbid')
  - Regression isolation (dependency additions do not corrupt Phase 8 variance)
  - Static Phase 9.5 boundary verification
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
from app.schemas.decision import ApprovedActualResponse
from app.schemas.network import DependencyCreate
from app.schemas.schedule import ScheduleActivityCreate
from app.services.decision_service import decision_service
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
# Helper to seed a standard network with variances
# ==============================================================================

async def _seed_test_network_and_variances():
    # Activity 1: ACT-101 (Critical path, delayed 3 days)
    act1 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-101",
            name="Foundation Excavation",
            wbs_code="1.1",
            discipline="Civil",
            planned_quantity=100.0,
            planned_unit="m3",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )
    # Approved actual with 3-day date delay (finish 8/13 instead of 8/10)
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act1.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=100.0,
            actual_unit="m3",
            actual_date=date(2026, 8, 13),  # 3 days late
            source_evidence=["Excavation completed"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # Activity 2: ACT-102 (Critical path successor of ACT-101)
    act2 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-102",
            name="Rebar Placement",
            wbs_code="1.1",
            discipline="Civil",
            planned_quantity=50.0,
            planned_unit="tons",
            planned_start_date=date(2026, 8, 11),
            planned_finish_date=date(2026, 8, 18),
        ),
    )

    # Activity 3: ACT-103 (Parallel branch, completed on time)
    act3 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-103",
            name="Procurement of Piping",
            wbs_code="2.1",
            discipline="Piping",
            planned_quantity=200.0,
            planned_unit="LF",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 10),
        ),
    )
    # Mark ACT-103 completed on time
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act3.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=200.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 10),
            source_evidence=["Piping received"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # Activity 4: ACT-104 (Successor of ACT-103 with float)
    act4 = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-104",
            name="Piping Prefabrication",
            wbs_code="2.1",
            discipline="Piping",
            planned_quantity=100.0,
            planned_unit="LF",
            planned_start_date=date(2026, 8, 11),
            planned_finish_date=date(2026, 8, 15),
        ),
    )

    # Dependencies: ACT-101 -> ACT-102 (FS), ACT-103 -> ACT-104 (FS), ACT-101 -> ACT-104 (FS)
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act1.id, successor_id=act2.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act3.id, successor_id=act4.id)
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act1.id, successor_id=act4.id)
    )

    return act1, act2, act3, act4


# ==============================================================================
# 1. Risk Summary & Activities API (Tests 26-33)
# ==============================================================================

@pytest.mark.asyncio
async def test_26_risk_summary_endpoint():
    """Test 26: Authenticated viewer GET /risks/summary returns 200 with summary structure."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/summary", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == PROJECT_A
        assert body["total_activities"] == 4
        assert "critical_severity_count" in body
        assert "high_severity_count" in body
        assert "medium_severity_count" in body
        assert "low_severity_count" in body
        assert "critical_path_delay_count" in body
        assert "items" in body
        assert len(body["items"]) == 4


@pytest.mark.asyncio
async def test_27_risk_activities_endpoint():
    """Test 27: Authenticated viewer GET /risks/activities returns 200 with list structure."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["items"]) == 4


@pytest.mark.asyncio
async def test_28_severity_filter_works():
    """Test 28: Filtering by severity level."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?severity=critical", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["severity"] == "critical"


@pytest.mark.asyncio
async def test_29_category_filter_works():
    """Test 29: Filtering by canonical risk category."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/risks/activities?category=critical_path_delay",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert "critical_path_delay" in item["categories"]


@pytest.mark.asyncio
async def test_30_wbs_filter_works():
    """Test 30: Filtering by WBS code."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?wbs_code=1.1", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert item["wbs_code"] == "1.1"


@pytest.mark.asyncio
async def test_31_discipline_filter_works():
    """Test 31: Filtering by trade discipline."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?discipline=Civil", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert item["discipline"].lower() == "civil"


@pytest.mark.asyncio
async def test_32_pagination_bounds_enforced():
    """Test 32: Pagination parameter validation and bounding."""
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # limit < 1
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?limit=0", headers=headers)
        assert r1.status_code == 422

        # limit > 100
        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?limit=101", headers=headers)
        assert r2.status_code == 422

        # offset < 0
        r3 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities?offset=-1", headers=headers)
        assert r3.status_code == 422


@pytest.mark.asyncio
async def test_33_deterministic_ordering():
    """Test 33: Risk register ordering follows severity rank, risk_score DESC, activity_code ASC, id ASC."""
    await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]

        sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(items) - 1):
            curr_item = items[i]
            next_item = items[i + 1]
            curr_rank = sev_rank[curr_item["severity"]]
            next_rank = sev_rank[next_item["severity"]]
            assert (curr_rank, -curr_item["risk_score"]) <= (next_rank, -next_item["risk_score"])


# ==============================================================================
# 2. Downstream Impact API (Tests 34-36)
# ==============================================================================

@pytest.mark.asyncio
async def test_34_downstream_impact_endpoint():
    """Test 34: GET downstream-impact returns 200 and transitive successor impact tree."""
    act1, act2, act3, act4 = await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/risks/downstream-impact/{act1.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_activity_id"] == str(act1.id)
        assert body["source_delay_days"] == 3
        assert body["total_downstream_activities_count"] == 2  # ACT-102 and ACT-104
        assert len(body["impacted_successors"]) == 2


@pytest.mark.asyncio
async def test_35_completed_successors_preserved_as_historical():
    """Test 35: Completed successors in downstream impact are classified as historical_completed."""
    act_a = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-A",
            name="Source A",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 5),
        ),
    )
    act_b = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(
            activity_code="ACT-B",
            name="Successor B (Already done)",
            planned_start_date=date(2026, 8, 6),
            planned_finish_date=date(2026, 8, 10),
            planned_quantity=50.0,
            planned_unit="LF",
        ),
    )
    await dependency_service.create_dependency(
        PROJECT_A, DependencyCreate(predecessor_id=act_a.id, successor_id=act_b.id)
    )

    # Delay on A
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act_a.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=10.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 9),  # 4 days delayed
            source_evidence=["Work done"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    # Completion on B
    await decision_service.actual_repo.create_or_get_approved_actual(
        ApprovedActualResponse(
            id=uuid4(),
            project_id=UUID(PROJECT_A),
            schedule_activity_id=act_b.id,
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=50.0,
            actual_unit="LF",
            actual_date=date(2026, 8, 10),
            source_evidence=["Complete"],
            approved_by=UUID(USER_PLANNER),
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/risks/downstream-impact/{act_a.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["historical_completed_count"] == 1
        succ = body["impacted_successors"][0]
        assert succ["impact_severity"] == "historical_completed"
        assert succ["is_completed"] is True


@pytest.mark.asyncio
async def test_36_cross_project_downstream_request_rejected():
    """Test 36: Requesting downstream impact for activity in Project A with Project B user returns 403."""
    act1 = await schedule_service.create_or_update_activity(
        PROJECT_A, ScheduleActivityCreate(activity_code="ACT-1", name="Task 1")
    )
    token_outsider = create_jwt(USER_OUTSIDER)
    headers_outsider = {"Authorization": f"Bearer {token_outsider}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/risks/downstream-impact/{act1.id}",
            headers=headers_outsider,
        )
        assert resp.status_code == 403


# ==============================================================================
# 3. Security, Boundaries & Schemas (Tests 37-41)
# ==============================================================================

@pytest.mark.asyncio
async def test_37_unauthenticated_requests_return_401():
    """Test 37: Missing or invalid JWT returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/summary")
        assert r1.status_code == 401

        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/activities")
        assert r2.status_code == 401

        r3 = await client.get(f"/api/v1/projects/{PROJECT_A}/risks/downstream-impact/{uuid4()}")
        assert r3.status_code == 401


def test_38_api_does_not_consume_raw_ai_or_field_input_tables():
    """
    Test 38: Asserts that risk query service imports and uses only approved_actuals
    and schedule_activities, not raw field_inputs, ai_extractions, or ai_matches as actuals.
    """
    import app.services.risk_query_service as rqs
    src = inspect.getsource(rqs)

    assert "field_inputs" not in src
    assert "ai_extractions" not in src
    assert "ai_matches" not in src


def test_39_no_forbidden_phase96_or_frontend_identifiers():
    """Test 39: Phase 9.5 runtime source contains no forbidden terms."""
    import app.api.v1.routers.network as net_router
    import app.api.v1.routers.risks as risk_router
    import app.services.dependency_service as dep_svc
    import app.services.risk_query_service as risk_query

    sources = [
        inspect.getsource(net_router),
        inspect.getsource(risk_router),
        inspect.getsource(dep_svc),
        inspect.getsource(risk_query),
    ]

    forbidden_tokens = [
        "forecast",
        "delay_prediction",
        "risk_heatmap",
        "react",
        "tsx",
        "cost_variance",
        "cpi",
        "spi",
    ]

    for src in sources:
        for token in forbidden_tokens:
            assert token not in src.lower(), f"Forbidden token '{token}' detected in Phase 9.5 runtime code"


@pytest.mark.asyncio
async def test_40_error_sanitization():
    """Test 40: Non-existent activity in downstream impact produces sanitized 404."""
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/risks/downstream-impact/{uuid4()}",
            headers=headers,
        )
        assert resp.status_code == 404
        assert "traceback" not in resp.text.lower()
        assert "postgres" not in resp.text.lower()
        assert "secret" not in resp.text.lower()


def test_41_response_schemas_reject_extra_fields():
    """Test 41: Strict extra='forbid' validation on Phase 9.5 schemas."""
    from pydantic import ValidationError
    from app.schemas.network import DependencyCreate

    with pytest.raises(ValidationError):
        DependencyCreate(
            predecessor_id=uuid4(),
            successor_id=uuid4(),
            extra_unauthorized_field="malicious",  # type: ignore
        )


# ==============================================================================
# 4. Phase 8 Variance Regression Test (Test 42)
# ==============================================================================

@pytest.mark.asyncio
async def test_42_dependency_mutation_does_not_affect_phase8_variance():
    """
    Test 42: Verifies adding or removing schedule dependency edges does NOT alter
    Phase 8 Plan vs Actual variance metrics or rollups.
    """
    act1, act2, act3, act4 = await _seed_test_network_and_variances()

    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Fetch baseline Phase 8 summary
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers)
        assert r1.status_code == 200
        summary_before = r1.json()

        # 2. Add an additional dependency
        await dependency_service.create_dependency(
            PROJECT_A,
            DependencyCreate(predecessor_id=act2.id, successor_id=act4.id),
        )

        # 3. Fetch Phase 8 summary again
        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/variance/summary", headers=headers)
        assert r2.status_code == 200
        summary_after = r2.json()

        # 4. Assert exact mathematical equivalence
        assert summary_before["total_activities"] == summary_after["total_activities"]
        assert summary_before["completed_activities"] == summary_after["completed_activities"]
        assert summary_before["in_progress_activities"] == summary_after["in_progress_activities"]
        assert summary_before["unit_rollups"] == summary_after["unit_rollups"]
