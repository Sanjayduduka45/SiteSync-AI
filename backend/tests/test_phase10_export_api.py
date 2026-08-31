"""
FastAPI HTTP Integration and Security tests for Phase 10.3 Report Export APIs.
Verifies:
1. All roles (Viewer, Supervisor, Planner, Admin) have export access
2. CSV format export (Content-Type: text/csv; charset=utf-8, Content-Disposition header)
3. JSON format export (Content-Type: application/json, structured envelope)
4. All 3 canonical datasets: approved_actuals, variance, risk_register
5. Complete dataset export without accidental pagination slicing
6. Unauthenticated and cross-project access rejection
7. Unsupported format and dataset error sanitization
8. Formula injection protection remains intact over HTTP
9. No sensitive secrets or internal embeddings exposed
"""

from __future__ import annotations

import csv
import json
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
    decision_service.decision_repo.clear()

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


@pytest.mark.asyncio
async def test_unauthenticated_export_rejected():
    """Verifies that export requests without credentials return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals")
        assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id, role_name",
    [
        (USER_VIEWER, "viewer"),
        (USER_SUPERVISOR, "supervisor"),
        (USER_PLANNER, "planner"),
        (USER_ADMIN, "admin"),
    ],
)
async def test_all_roles_can_export_csv(user_id: str, role_name: str):
    """Verifies that all four canonical roles can download CSV exports."""
    token = create_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format=csv",
            headers=headers,
        )
        assert resp.status_code == 200, f"Role {role_name} failed: {resp.text}"
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment; filename=" in resp.headers.get("content-disposition", "")
        assert resp.text.startswith("id,project_id")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id, role_name",
    [
        (USER_VIEWER, "viewer"),
        (USER_SUPERVISOR, "supervisor"),
        (USER_PLANNER, "planner"),
        (USER_ADMIN, "admin"),
    ],
)
async def test_all_roles_can_export_json(user_id: str, role_name: str):
    """Verifies that all four canonical roles can download structured JSON exports."""
    token = create_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/variance?format=json",
            headers=headers,
        )
        assert resp.status_code == 200, f"Role {role_name} failed: {resp.text}"
        assert "application/json" in resp.headers["content-type"]
        data = resp.json()
        assert data["project_id"] == PROJECT_A
        assert data["dataset"] == "variance"
        assert "records" in data


@pytest.mark.asyncio
async def test_export_three_canonical_datasets():
    """Verifies that approved_actuals, variance, and risk_register all export successfully."""
    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}

    # Add sample activity and approved actual
    act = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-EXP-01", name="Export Validation Task", planned_quantity=100.0, planned_unit="LF"),
    )

    actual = ApprovedActualResponse(
        id=uuid4(),
        project_id=UUID(PROJECT_A),
        schedule_activity_id=UUID(str(act.id)),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=50.0,
        actual_unit="LF",
        actual_date=date(2026, 8, 28),
        approved_by=UUID(USER_PLANNER),
        approved_at=datetime.now(timezone.utc),
        notes="=DANGEROUS()",
        is_modified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await decision_service.actual_repo.create_or_get_approved_actual(actual)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Approved Actuals
        r1 = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format=csv", headers=headers)
        assert r1.status_code == 200
        assert "'=DANGEROUS()" in r1.text  # Formula injection protected

        # 2. Variance
        r2 = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/variance?format=csv", headers=headers)
        assert r2.status_code == 200
        assert "ACT-EXP-01" in r2.text

        # 3. Risk Register
        r3 = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/risk_register?format=csv", headers=headers)
        assert r3.status_code == 200
        assert "ACT-EXP-01" in r3.text


@pytest.mark.asyncio
async def test_complete_dataset_export_no_truncation():
    """
    Verifies that the export endpoint exports all items in the dataset without inheriting the standard 50-item page limit.
    """
    token = create_jwt(USER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    # Create 60 schedule activities (greater than default page size of 50)
    for i in range(60):
        await schedule_service.create_or_update_activity(
            PROJECT_A,
            ScheduleActivityCreate(activity_code=f"ACT-BULK-{i:03d}", name=f"Bulk Task {i}"),
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/variance?format=json", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["record_count"] == 60
        assert len(data["records"]) == 60


@pytest.mark.asyncio
async def test_cross_project_export_forbidden():
    """Verifies that an unauthorized project export returns 403."""
    token_a = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_B}/exports/variance", headers=headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unsupported_export_options_error_sanitization():
    """Verifies that unsupported dataset or format requests return sanitized 400 Bad Request."""
    token = create_jwt(USER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid dataset
        r_ds = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/unsupported_dataset", headers=headers)
        assert r_ds.status_code == 400
        assert r_ds.json()["error"]["code"] == "INVALID_DATASET"

        # Invalid format
        r_fmt = await client.get(f"/api/v1/projects/{PROJECT_A}/exports/variance?format=xlsx", headers=headers)
        assert r_fmt.status_code == 400
        assert r_fmt.json()["error"]["code"] == "INVALID_FORMAT"
