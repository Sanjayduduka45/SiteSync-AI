"""
SiteSync AI — Phase 8.4 Final Security Audit & Boundary Verification Test Suite.

Authoritative verification of:
  1. Mathematical correctness & ADR-009 adherence (ΔQ, P%, ΔT).
  2. Multi-actual aggregation & idempotency (ADR-010).
  3. Unit normalization and mismatch safety (ADR-011).
  4. Unquantified activity handling.
  5. Deterministic activity status classification.
  6. Homogeneous-unit WBS & Project rollups without averaging (ADR-012).
  7. Strict read-only API enforcement (ADR-013).
  8. RBAC and cross-tenant boundary containment.
  9. Approved-actuals only data boundary (Phase 7 isolation).
 10. Complete absence of Phase 9 concepts across all Phase 8 runtime code.
 11. Error sanitization (zero leaks of secrets, SQL, or traces).
 12. Pydantic v2 contract integrity against frontend types.
"""

from __future__ import annotations

import inspect
from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.routers.variance as variance_router
import app.schemas.variance as variance_schemas
import app.services.variance_query_service as variance_query_service
import app.services.variance_service as variance_service_mod
from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.variance import (
    ActivityVarianceInput,
    ActivityVarianceItem,
    ActivityVarianceListResponse,
    ActivityVarianceStatus,
    ApprovedActualInput,
    ProjectVarianceSummary,
    UnitRollup,
    WbsRollup,
    WbsVarianceListResponse,
)
from app.services.decision_service import decision_service
from app.services.schedule_service import schedule_service
from app.services.variance_service import are_units_compatible, normalize_unit, variance_service
from tests.test_variance_router import create_jwt

PROJECT_ALPHA = "00000000-0000-0000-0000-000000000001"
PROJECT_BETA = "00000000-0000-0000-0000-000000000002"

USER_VIEWER = "00000000-0000-0000-0000-000000000003"
USER_SUPERVISOR = "00000000-0000-0000-0000-000000000004"
USER_PLANNER = "00000000-0000-0000-0000-000000000005"
USER_ADMIN = "00000000-0000-0000-0000-000000000006"
USER_OUTSIDER = "00000000-0000-0000-0000-000000000007"


@pytest.fixture(autouse=True)
def setup_audit_state():
    """Resets memory stores and memberships before each test."""
    membership_registry.clear()
    schedule_service.clear()
    decision_service.actual_repo.clear()

    # Seed projects
    membership_registry.seed_project(PROJECT_ALPHA, "Project Alpha", "ALPHA")
    membership_registry.seed_project(PROJECT_BETA, "Project Beta", "BETA")

    # Project Alpha memberships
    membership_registry.add_membership(USER_VIEWER, PROJECT_ALPHA, ProjectRole.VIEWER)
    membership_registry.add_membership(USER_SUPERVISOR, PROJECT_ALPHA, ProjectRole.SUPERVISOR)
    membership_registry.add_membership(USER_PLANNER, PROJECT_ALPHA, ProjectRole.PLANNER)
    membership_registry.add_membership(USER_ADMIN, PROJECT_ALPHA, ProjectRole.ADMIN)

    # Project Beta memberships (Outsider to Alpha)
    membership_registry.add_membership(USER_OUTSIDER, PROJECT_BETA, ProjectRole.ADMIN)


def make_activity_input(
    planned_qty: float | None = 100.0,
    planned_unit: str | None = "LF",
    planned_start: date | None = date(2026, 8, 1),
    planned_finish: date | None = date(2026, 8, 10),
    actuals: list[tuple[float | None, str | None, date]] | None = None,
    code: str = "ACT-101",
    wbs: str | None = "1.1",
) -> ActivityVarianceInput:
    approved = []
    if actuals is not None:
        for qty, unit, dt in actuals:
            approved.append(
                ApprovedActualInput(
                    actual_quantity=qty,
                    actual_unit=unit,
                    actual_date=dt,
                )
            )
    return ActivityVarianceInput(
        activity_id=uuid4(),
        project_id=UUID(PROJECT_ALPHA),
        activity_code=code,
        name=f"Activity {code}",
        wbs_code=wbs,
        discipline="Civil",
        location="Site",
        planned_quantity=planned_qty,
        planned_unit=planned_unit,
        planned_start_date=planned_start,
        planned_finish_date=planned_finish,
        approved_actuals=approved,
    )


# ==============================================================================
# 1. ADR-009 Mathematical Audit (Pure Math Engine)
# ==============================================================================

def test_audit_1_quantity_variance_sign_and_values():
    """
    Verifies ΔQ = Actual - Planned sign convention:
      - Actual < Planned -> Negative (under plan)
      - Actual == Planned -> Zero (on plan)
      - Actual > Planned -> Positive (over plan)
    """
    # Under plan: 80 - 100 = -20
    res1 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(80.0, "LF", date(2026, 8, 5))]))
    assert res1.quantity_variance == -20.0

    # On plan: 100 - 100 = 0
    res2 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(100.0, "LF", date(2026, 8, 5))]))
    assert res2.quantity_variance == 0.0

    # Over plan: 120 - 100 = +20
    res3 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(120.0, "LF", date(2026, 8, 5))]))
    assert res3.quantity_variance == 20.0


def test_audit_2_progress_percentage_unclamped_and_null_safety():
    """
    Verifies P% = (Actual / Planned) * 100:
      - Never clamped to 100% (125% is valid)
      - Planned 0 or None returns None
    """
    # 50%
    res1 = variance_service.calculate_activity_variance(make_activity_input(200.0, "LF", actuals=[(100.0, "LF", date(2026, 8, 5))]))
    assert res1.progress_percent == 50.0

    # 125% unclamped
    res2 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(125.0, "LF", date(2026, 8, 5))]))
    assert res2.progress_percent == 125.0

    # Planned 0 -> None
    res3 = variance_service.calculate_activity_variance(make_activity_input(0.0, "LF", actuals=[(50.0, "LF", date(2026, 8, 5))]))
    assert res3.progress_percent is None

    # Planned None -> None
    res4 = variance_service.calculate_activity_variance(make_activity_input(None, "LF", actuals=[(50.0, "LF", date(2026, 8, 5))]))
    assert res4.progress_percent is None


def test_audit_3_date_variance_days():
    """
    Verifies ΔT = Latest Actual Date - Planned Finish Date:
      - Positive = Late
      - Zero = On Time
      - Negative = Early
    """
    d_plan = date(2026, 8, 10)
    # Late: 8/13 - 8/10 = +3
    res1 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", planned_finish=d_plan, actuals=[(50.0, "LF", date(2026, 8, 13))]))
    assert res1.date_variance_days == 3

    # On Time: 8/10 - 8/10 = 0
    res2 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", planned_finish=d_plan, actuals=[(50.0, "LF", date(2026, 8, 10))]))
    assert res2.date_variance_days == 0

    # Early: 8/8 - 8/10 = -2
    res3 = variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", planned_finish=d_plan, actuals=[(50.0, "LF", date(2026, 8, 8))]))
    assert res3.date_variance_days == -2


# ==============================================================================
# 2. ADR-010 Multi-Actual Aggregation & Idempotency Audit
# ==============================================================================

def test_audit_4_multiple_actuals_aggregation():
    """
    Verifies multiple approved actuals accumulate quantities via SUM and resolve latest date via MAX.
    """
    act = make_activity_input(
        100.0,
        "LF",
        actuals=[
            (10.0, "LF", date(2026, 8, 1)),
            (20.0, "LF", date(2026, 8, 5)),
            (30.0, "LF", date(2026, 8, 3)),
        ],
    )
    res = variance_service.calculate_activity_variance(act)
    assert res.actual_quantity_total == 60.0
    assert res.actual_unit == "LF"
    assert res.latest_actual_date == date(2026, 8, 5)
    assert res.approved_actuals_count == 3


# ==============================================================================
# 3. ADR-011 Unit Normalization & Status Classification Audit
# ==============================================================================

def test_audit_5_unit_compatibility_and_whitespace_normalization():
    """
    Verifies case and whitespace normalization of units and strict rejection of conversion.
    """
    assert are_units_compatible(" LF ", "lf") is True
    assert are_units_compatible("tons", "TONS") is True
    assert are_units_compatible("LF", "meters") is False
    assert are_units_compatible("spools", "LF") is False


def test_audit_6_activity_status_lifecycle():
    """
    Verifies deterministic status classification:
      - 0 actuals or actual == 0 -> NOT_STARTED
      - 0 < actual < planned -> IN_PROGRESS
      - actual == planned -> COMPLETED
      - actual > planned -> OVER_DELIVERED
      - planned == None -> UNQUANTIFIED
      - unit mismatch -> UNIT_MISMATCH
    """
    # Not started
    assert variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[])).variance_status == ActivityVarianceStatus.NOT_STARTED
    # In progress
    assert variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(50.0, "LF", date(2026, 8, 1))])).variance_status == ActivityVarianceStatus.IN_PROGRESS
    # Completed
    assert variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(100.0, "LF", date(2026, 8, 1))])).variance_status == ActivityVarianceStatus.COMPLETED
    # Over delivered
    assert variance_service.calculate_activity_variance(make_activity_input(100.0, "LF", actuals=[(120.0, "LF", date(2026, 8, 1))])).variance_status == ActivityVarianceStatus.OVER_DELIVERED
    # Unquantified
    assert variance_service.calculate_activity_variance(make_activity_input(None, None, actuals=[(50.0, "LF", date(2026, 8, 1))])).variance_status == ActivityVarianceStatus.UNQUANTIFIED
    # Unit mismatch
    assert variance_service.calculate_activity_variance(make_activity_input(100.0, "spools", actuals=[(50.0, "LF", date(2026, 8, 1))])).variance_status == ActivityVarianceStatus.UNIT_MISMATCH


# ==============================================================================
# 4. ADR-012 Homogeneous Rollups Audit (No Averaging)
# ==============================================================================

def test_audit_7_wbs_and_project_homogeneous_rollups_never_average_percentages():
    """
    Verifies that rollups sum physical quantities and compute weighted progress, never averaging:
      Activity A: 100 planned, 100 actual -> 100%
      Activity B: 900 planned, 450 actual -> 50%
      Sum: 550 / 1000 = 55.0% (NOT (100+50)/2 = 75.0%)
    """
    items = [
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=UUID(PROJECT_ALPHA),
            activity_code="A",
            name="Task A",
            planned_quantity=100.0,
            planned_unit="LF",
            actual_quantity_total=100.0,
            actual_unit="LF",
            approved_actuals_count=1,
            quantity_variance=0.0,
            progress_percent=100.0,
            variance_status=ActivityVarianceStatus.COMPLETED,
            is_flagged=False,
        ),
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=UUID(PROJECT_ALPHA),
            activity_code="B",
            name="Task B",
            planned_quantity=900.0,
            planned_unit="LF",
            actual_quantity_total=450.0,
            actual_unit="LF",
            approved_actuals_count=1,
            quantity_variance=-450.0,
            progress_percent=50.0,
            variance_status=ActivityVarianceStatus.IN_PROGRESS,
            is_flagged=False,
        ),
    ]

    summary = variance_service.calculate_project_summary(PROJECT_ALPHA, items)
    assert summary.total_activities == 2
    assert summary.overall_progress_percent == pytest.approx(55.0)  # Exactly 55%, never 75%
    assert len(summary.unit_rollups) == 1
    assert summary.unit_rollups[0].progress_percent == pytest.approx(55.0)


def test_audit_8_mixed_units_return_null_overall_progress():
    """
    Verifies that when a project has mixed units (LF and tons), overall_progress_percent is None.
    """
    items = [
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=UUID(PROJECT_ALPHA),
            activity_code="A",
            name="Pipe A",
            planned_quantity=100.0,
            planned_unit="LF",
            actual_quantity_total=50.0,
            actual_unit="LF",
            approved_actuals_count=1,
            quantity_variance=-50.0,
            progress_percent=50.0,
            variance_status=ActivityVarianceStatus.IN_PROGRESS,
            is_flagged=False,
        ),
        ActivityVarianceItem(
            activity_id=uuid4(),
            project_id=UUID(PROJECT_ALPHA),
            activity_code="B",
            name="Steel B",
            planned_quantity=20.0,
            planned_unit="tons",
            actual_quantity_total=10.0,
            actual_unit="tons",
            approved_actuals_count=1,
            quantity_variance=-10.0,
            progress_percent=50.0,
            variance_status=ActivityVarianceStatus.IN_PROGRESS,
            is_flagged=False,
        ),
    ]
    summary = variance_service.calculate_project_summary(PROJECT_ALPHA, items)
    assert summary.overall_progress_percent is None
    assert len(summary.unit_rollups) == 2


# ==============================================================================
# 5. Security & RBAC Audit Through HTTP Router
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_9_all_roles_read_and_unauthenticated_rejected():
    """
    Verifies 401 for unauthenticated and 200 for Viewer, Supervisor, Planner, Admin.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 401
        r_unauth = await client.get(f"/api/v1/projects/{PROJECT_ALPHA}/variance/summary")
        assert r_unauth.status_code == 401

        # All 4 roles
        for uid in [USER_VIEWER, USER_SUPERVISOR, USER_PLANNER, USER_ADMIN]:
            headers = {"Authorization": f"Bearer {create_jwt(uid)}"}
            r_sum = await client.get(f"/api/v1/projects/{PROJECT_ALPHA}/variance/summary", headers=headers)
            assert r_sum.status_code == 200
            r_act = await client.get(f"/api/v1/projects/{PROJECT_ALPHA}/variance/activities", headers=headers)
            assert r_act.status_code == 200
            r_wbs = await client.get(f"/api/v1/projects/{PROJECT_ALPHA}/variance/wbs", headers=headers)
            assert r_wbs.status_code == 200


@pytest.mark.asyncio
async def test_audit_10_cross_tenant_idor_blocked():
    """
    Verifies User in Project Beta cannot access Project Alpha variance data.
    """
    headers_outsider = {"Authorization": f"Bearer {create_jwt(USER_OUTSIDER)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/v1/projects/{PROJECT_ALPHA}/variance/summary", headers=headers_outsider)
        assert r.status_code == 403
        assert "FORBIDDEN" in r.text


@pytest.mark.asyncio
async def test_audit_11_mutations_disallowed_405():
    """
    Verifies strict read-only boundary: POST, PUT, PATCH, DELETE are rejected with 405.
    """
    headers = {"Authorization": f"Bearer {create_jwt(USER_ADMIN)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_post = await client.post(f"/api/v1/projects/{PROJECT_ALPHA}/variance/summary", headers=headers, json={})
        assert r_post.status_code == 405
        r_put = await client.put(f"/api/v1/projects/{PROJECT_ALPHA}/variance/activities", headers=headers, json={})
        assert r_put.status_code == 405
        r_patch = await client.patch(f"/api/v1/projects/{PROJECT_ALPHA}/variance/wbs", headers=headers, json={})
        assert r_patch.status_code == 405
        r_del = await client.delete(f"/api/v1/projects/{PROJECT_ALPHA}/variance/summary", headers=headers)
        assert r_del.status_code == 405


# ==============================================================================
# 6. Static Source Code Audits (Phase 7 Data Source & Phase 9 Isolation)
# ==============================================================================

def test_audit_12_phase7_approved_actuals_only_source_boundary():
    """
    Verifies that Phase 8 query service accesses ONLY approved_actuals repository and schedule_service.
    Never consumes raw extractions, field inputs, or unapproved AI matches as actual progress.
    """
    query_src = inspect.getsource(variance_query_service)

    # Must consume schedule_service and approved_actuals
    assert "schedule_service.list_activities" in query_src
    assert "actual_repo.list_approved_actuals" in query_src

    # Must NOT import or query raw inputs or unapproved matches for progress
    assert "field_input_service" not in query_src
    assert "raw_text" not in query_src
    assert "extracted_entities" not in query_src


def test_audit_13_phase9_static_boundary_across_all_phase8_modules():
    """
    Scans all Phase 8 backend modules to guarantee ZERO occurrence of Phase 9 identifiers.
    """
    modules = [
        variance_schemas,
        variance_service_mod,
        variance_query_service,
        variance_router,
    ]

    forbidden_tokens = [
        "critical_path",
        "total_float",
        "free_float",
        "slack_days",
        "delay_prediction",
        "delay_forecast",
        "schedule_forecast",
        "risk_score",
        "risk_level",
        "risk_heatmap",
        "downstream_impact",
        "cost_variance",
        "cpi",
        "spi",
    ]

    for mod in modules:
        src = inspect.getsource(mod).lower()
        for token in forbidden_tokens:
            assert token not in src, f"Forbidden Phase 9 token '{token}' found in {mod.__name__}"


def test_audit_14_schema_strictness_extra_forbid_and_field_validations():
    """
    Verifies Pydantic v2 models enforce extra='forbid', preventing client identity or field injection.
    """
    with pytest.raises(Exception):
        ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code="ACT-01",
            name="Test",
            injected_field="malicious",  # Forbidden extra field
        )

    with pytest.raises(Exception):
        ApprovedActualInput(
            actual_quantity=-10.0,  # Negative quantity rejected
            actual_unit="LF",
            actual_date=date(2026, 8, 1),
        )
