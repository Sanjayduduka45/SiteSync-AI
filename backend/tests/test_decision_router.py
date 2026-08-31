"""
SiteSync AI — Phase 7.4 Decision Router Unit & Security Tests.
Covers:
  1. unauthenticated approve -> 401
  2. unauthenticated reject -> 401
  3. unauthenticated modify -> 401
  4. viewer approve -> 403
  5. supervisor approve -> 403
  6. planner approve -> allowed (200)
  7. admin approve -> allowed (200)
  8. viewer can read decision -> 200
  9. supervisor can read decision -> 200
  10. planner can read decision -> 200
  11. admin can read decision -> 200
  12. viewer can read approved actuals -> 200
  13. supervisor can read approved actuals -> 200
  14. planner can read approved actuals -> 200
  15. admin can read approved actuals -> 200
  16. cross-project match cannot be approved -> 403/404
  17. cross-project match cannot be rejected -> 403/404
  18. cross-project match cannot be modified -> 403/404
  19. cross-project decision cannot be read -> 200 null
  20. client cannot override planner identity
  21. client cannot override project_id
  22. client cannot override approved_by
  23. client cannot override decision
  24. reject requires reason
  25. modify validates quantity
  26. modify validates UUID
  27. invalid date range rejected
  28. missing match returns controlled 404
  29. missing decision returns 200 null
  30. approved actual pagination works
  31. schedule_activity_id filter works
  32. date filters work
  33. API errors contain no secrets
  34. API errors contain no stack trace
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.decision import (
    ApprovedActualResponse,
    PlannerDecisionResponse,
    PlannerDecisionType,
    RejectMatchRequest,
)
from app.schemas.schedule import (
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScoringBreakdown,
)
from app.services.decision_service import decision_service
from app.services.extraction_service import extraction_service
from app.services.matching_service import matching_service
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


PROJECT_A_ID = "00000000-0000-0000-0000-000000000001"
PROJECT_B_ID = "00000000-0000-0000-0000-000000000002"
USER_ADMIN = "00000000-0000-0000-0000-0000000000a1"
USER_PLANNER = "00000000-0000-0000-0000-0000000000b1"
USER_SUPERVISOR = "00000000-0000-0000-0000-0000000000c1"
USER_VIEWER = "00000000-0000-0000-0000-0000000000d1"
USER_OUTSIDER = "00000000-0000-0000-0000-0000000000e1"



@pytest.fixture(autouse=True)
def setup_test_state():
    """Resets registries, services, and repositories before each test."""
    membership_registry.clear()
    schedule_service.clear()
    extraction_service.clear()
    matching_service.repository.clear()
    decision_service.decision_repo.clear()
    decision_service.actual_repo.clear()

    # Seed projects
    membership_registry.seed_project(PROJECT_A_ID, "Project Alpha", "ALPHA")
    membership_registry.seed_project(PROJECT_B_ID, "Project Beta", "BETA")

    # Project A members
    membership_registry.add_membership(USER_ADMIN, PROJECT_A_ID, ProjectRole.ADMIN)
    membership_registry.add_membership(USER_PLANNER, PROJECT_A_ID, ProjectRole.PLANNER)
    membership_registry.add_membership(USER_SUPERVISOR, PROJECT_A_ID, ProjectRole.SUPERVISOR)
    membership_registry.add_membership(USER_VIEWER, PROJECT_A_ID, ProjectRole.VIEWER)

    # Project B members (Outsider to A)
    membership_registry.add_membership(USER_OUTSIDER, PROJECT_B_ID, ProjectRole.ADMIN)


async def _seed_match_infrastructure(
    project_id: str = PROJECT_A_ID,
    activity_code: str = "ACT-STEEL-01",
    activity_name: str = "Erect Structural Steel Tier 1",
    progress_val: float = 12.0,
    progress_unit: str = "tons",
) -> tuple[str, str, str]:
    """Helper to seed activity, extraction, and AI match recommendation."""
    # 1. Schedule Activity
    act = await schedule_service.create_or_update_activity(
        project_id,
        ScheduleActivityCreate(
            activity_code=activity_code,
            name=activity_name,
            discipline="Civil",
            location="Grid 4",
            planned_start_date=date(2026, 9, 1),
            planned_finish_date=date(2026, 9, 15),
            planned_quantity=200.0,
            planned_unit=progress_unit,
        ),
    )
    sched_id = str(act.id)

    # 2. Completed Extraction
    ext_id = str(uuid4())
    now = datetime.now(timezone.utc)
    extraction_service.repository._records_by_id[ext_id] = {
        "id": ext_id,
        "project_id": project_id,
        "field_input_id": str(uuid4()),
        "status": "completed",
        "extracted_data": {
            "raw_input_id": "inp-test-1",
            "extracted_activities": [
                {
                    "description": f"Erected {progress_val} {progress_unit} in Grid 4",
                    "progress_value": progress_val,
                    "progress_unit": progress_unit,
                    "discipline": "Civil",
                    "location": "Grid 4",
                    "event_date": "2026-08-30",
                    "evidence_tokens": ["erected", f"{progress_val} {progress_unit}", "Grid 4"],
                }
            ],
            "extraction_confidence": 0.95,
            "model_version": "gemini-1.5-flash:v1",
        },
        "confidence_score": 0.95,
        "model_version": "gemini-1.5-flash:v1",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    # 3. Match Recommendation
    match_id = str(uuid4())
    match_rec = MatchRecommendationResponse(
        id=UUID(match_id),
        project_id=UUID(project_id),
        extraction_id=UUID(ext_id),
        activity_index=0,
        recommended_activity_id=UUID(sched_id),
        recommended_activity_code=activity_code,
        recommended_activity_name=activity_name,
        confidence_score=0.92,
        scoring_breakdown=ScoringBreakdown(
            semantic_similarity=0.90,
            discipline_contribution=0.15,
            location_contribution=0.10,
            temporal_contribution=0.05,
        ),
        alternative_matches=[],
        created_at=now,
        updated_at=now,
    )
    await matching_service.repository.upsert_match(match_rec)

    return sched_id, ext_id, match_id


# ==============================================================================
# 1-3. Unauthenticated Requests Return 401
# ==============================================================================

@pytest.mark.asyncio
async def test_1_unauthenticated_approve_returns_401():
    """Unauthenticated approve endpoint returns 401."""
    match_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve", json={"notes": "test"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_2_unauthenticated_reject_returns_401():
    """Unauthenticated reject endpoint returns 401."""
    match_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            json={"rejection_reason": "Not related"},
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_3_unauthenticated_modify_returns_401():
    """Unauthenticated modify endpoint returns 401."""
    match_id = str(uuid4())
    act_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/modify",
            json={
                "schedule_activity_id": act_id,
                "actual_quantity": 10.0,
                "actual_unit": "tons",
                "actual_date": "2026-08-30",
            },
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


# ==============================================================================
# 4-7. RBAC for Mutation Endpoints (Approve / Reject / Modify)
# ==============================================================================

@pytest.mark.asyncio
async def test_4_viewer_approve_returns_403():
    """Viewer role cannot approve matches (returns 403)."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_VIEWER),
            json={"notes": "Viewer attempt"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_5_supervisor_approve_returns_403():
    """Supervisor role cannot approve matches (returns 403)."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_SUPERVISOR),
            json={"notes": "Supervisor attempt"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_6_planner_approve_allowed():
    """Planner role can approve matches (returns 200 + ApprovedActualResponse)."""
    sched_id, ext_id, match_id = await _seed_match_infrastructure(progress_val=15.0, progress_unit="tons")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Approved by planner"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["match_id"] == match_id
        assert data["schedule_activity_id"] == sched_id
        assert data["project_id"] == PROJECT_A_ID
        assert data["actual_quantity"] == 15.0
        assert data["actual_unit"] == "tons"
        assert data["approved_by"] == USER_PLANNER
        assert data["notes"] == "Approved by planner"
        assert data["is_modified"] is False


@pytest.mark.asyncio
async def test_7_admin_approve_allowed():
    """Admin role can approve matches (returns 200 + ApprovedActualResponse)."""
    sched_id, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_ADMIN),
            json={},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["match_id"] == match_id
        assert data["approved_by"] == USER_ADMIN


# ==============================================================================
# 8-11. RBAC for Reading Decisions
# ==============================================================================

@pytest.mark.asyncio
async def test_8_viewer_can_read_decision():
    """Viewer can read decision audit record."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Not applicable to this phase"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_VIEWER),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["match_id"] == match_id
        assert data["decision"] == "rejected"
        assert data["decided_by"] == USER_PLANNER


@pytest.mark.asyncio
async def test_9_supervisor_can_read_decision():
    """Supervisor can read decision audit record."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Not applicable"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "rejected"


@pytest.mark.asyncio
async def test_10_planner_can_read_decision():
    """Planner can read decision audit record."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Not applicable"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_PLANNER),
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "rejected"


@pytest.mark.asyncio
async def test_11_admin_can_read_decision():
    """Admin can read decision audit record."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Not applicable"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_ADMIN),
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "rejected"


# ==============================================================================
# 12-15. RBAC for Reading Approved Actuals
# ==============================================================================

@pytest.mark.asyncio
async def test_12_viewer_can_read_approved_actuals():
    """Viewer can list approved actuals."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Approved for test"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals",
            headers=auth_header(USER_VIEWER),
        )
        assert res.status_code == 200
        assert res.json()["total"] == 1


@pytest.mark.asyncio
async def test_13_supervisor_can_read_approved_actuals():
    """Supervisor can list approved actuals."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Approved for test"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert res.status_code == 200
        assert res.json()["total"] == 1


@pytest.mark.asyncio
async def test_14_planner_can_read_approved_actuals():
    """Planner can list approved actuals."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Approved for test"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals",
            headers=auth_header(USER_PLANNER),
        )
        assert res.status_code == 200
        assert res.json()["total"] == 1


@pytest.mark.asyncio
async def test_15_admin_can_read_approved_actuals():
    """Admin can list approved actuals."""
    _, _, match_id = await _seed_match_infrastructure()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Approved for test"},
        )
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals",
            headers=auth_header(USER_ADMIN),
        )
        assert res.status_code == 200
        assert res.json()["total"] == 1



# ==============================================================================
# 16-19. Cross-Project Isolation & Containment
# ==============================================================================

@pytest.mark.asyncio
async def test_16_cross_project_match_cannot_be_approved():
    """Attempting to approve a Project B match via Project A URL returns 404 or 403."""
    _, _, match_b_id = await _seed_match_infrastructure(project_id=PROJECT_B_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_b_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Cross-project exploit"},
        )
        assert res.status_code in (403, 404)
        assert "error" in res.json()


@pytest.mark.asyncio
async def test_17_cross_project_match_cannot_be_rejected():
    """Attempting to reject a Project B match via Project A URL returns 404 or 403."""
    _, _, match_b_id = await _seed_match_infrastructure(project_id=PROJECT_B_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_b_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Cross project reject"},
        )
        assert res.status_code in (403, 404)
        assert "error" in res.json()


@pytest.mark.asyncio
async def test_18_cross_project_match_cannot_be_modified():
    """Attempting to modify a Project B match via Project A URL returns 404 or 403."""
    sched_a_id, _, _ = await _seed_match_infrastructure(project_id=PROJECT_A_ID)
    _, _, match_b_id = await _seed_match_infrastructure(project_id=PROJECT_B_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_b_id}/modify",
            headers=auth_header(USER_PLANNER),
            json={
                "schedule_activity_id": sched_a_id,
                "actual_quantity": 25.0,
                "actual_unit": "tons",
                "actual_date": "2026-08-30",
            },
        )
        assert res.status_code in (403, 404)
        assert "error" in res.json()


@pytest.mark.asyncio
async def test_19_cross_project_decision_cannot_be_read():
    """Querying Project B's decision through Project A returns 200 null (not exposing Beta)."""
    _, _, match_b_id = await _seed_match_infrastructure(project_id=PROJECT_B_ID)

    # Reject on Project B
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_rej = await client.post(
            f"/api/v1/projects/{PROJECT_B_ID}/matches/{match_b_id}/reject",
            headers=auth_header(USER_OUTSIDER),
            json={"rejection_reason": "Project B rejection"},
        )
        assert res_rej.status_code == 200

        # Query through Project A with Planner A credentials
        res_get = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_b_id}/decision",
            headers=auth_header(USER_PLANNER),
        )
        assert res_get.status_code == 200
        assert res_get.json() is None


# ==============================================================================
# 20-23. Tamper Resistance: Client Overrides Prohibited
# ==============================================================================

@pytest.mark.asyncio
async def test_20_client_cannot_override_planner_identity():
    """Client cannot inject a fake planner_id / decided_by in payload."""
    _, _, match_id = await _seed_match_infrastructure()
    fake_user = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # On approve: extra fields are forbidden
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Normal note", "planner_id": fake_user, "approved_by": fake_user},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_21_client_cannot_override_project_id():
    """Client cannot inject project_id into request body."""
    _, _, match_id = await _seed_match_infrastructure()
    fake_proj = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_PLANNER),
            json={"project_id": fake_proj},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_22_client_cannot_override_approved_by():
    """Client cannot inject approved_by in modify request."""
    sched_id, _, match_id = await _seed_match_infrastructure()
    fake_user = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/modify",
            headers=auth_header(USER_PLANNER),
            json={
                "schedule_activity_id": sched_id,
                "actual_quantity": 10.0,
                "actual_date": "2026-08-30",
                "approved_by": fake_user,
            },
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_23_client_cannot_override_decision():
    """Client cannot inject decision or timestamp fields into rejection body."""
    _, _, match_id = await _seed_match_infrastructure()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={
                "rejection_reason": "Valid reason",
                "decision": "approved",
                "decided_at": "2026-01-01T00:00:00Z",
            },
        )
        assert res.status_code == 422


# ==============================================================================
# 24-27. Input Validation Edge Cases
# ==============================================================================

@pytest.mark.asyncio
async def test_24_reject_requires_reason():
    """Rejection requires non-empty, non-whitespace reason."""
    _, _, match_id = await _seed_match_infrastructure()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing reason
        res_missing = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={},
        )
        assert res_missing.status_code == 422

        # Empty reason
        res_empty = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": ""},
        )
        assert res_empty.status_code == 422

        # Whitespace-only reason
        res_ws = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "   \n\t   "},
        )
        assert res_ws.status_code == 422


@pytest.mark.asyncio
async def test_25_modify_validates_quantity():
    """Modify rejects negative actual_quantity."""
    sched_id, _, match_id = await _seed_match_infrastructure()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/modify",
            headers=auth_header(USER_PLANNER),
            json={
                "schedule_activity_id": sched_id,
                "actual_quantity": -5.0,
                "actual_date": "2026-08-30",
            },
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_26_modify_validates_uuid():
    """Modify rejects non-UUID schedule_activity_id."""
    _, _, match_id = await _seed_match_infrastructure()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/modify",
            headers=auth_header(USER_PLANNER),
            json={
                "schedule_activity_id": "not-a-valid-uuid",
                "actual_quantity": 10.0,
                "actual_date": "2026-08-30",
            },
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_27_invalid_date_range_rejected():
    """Approved actuals query rejects from_date > to_date with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?from_date=2026-09-15&to_date=2026-09-01",
            headers=auth_header(USER_VIEWER),
        )
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "INVALID_DATE_RANGE"


# ==============================================================================
# 28-29. Missing Resources & Null Returns
# ==============================================================================

@pytest.mark.asyncio
async def test_28_missing_match_returns_controlled_404():
    """Approving or rejecting a non-existent match returns 404."""
    non_existent_match = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_app = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{non_existent_match}/approve",
            headers=auth_header(USER_PLANNER),
            json={"notes": "Notes"},
        )
        assert res_app.status_code == 404
        assert res_app.json()["error"]["code"] == "MATCH_NOT_FOUND"

        res_rej = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{non_existent_match}/reject",
            headers=auth_header(USER_PLANNER),
            json={"rejection_reason": "Does not exist"},
        )
        assert res_rej.status_code == 404
        assert res_rej.json()["error"]["code"] == "MATCH_NOT_FOUND"


@pytest.mark.asyncio
async def test_29_missing_decision_returns_200_null():
    """GET decision on a match with no recorded decision returns 200 null."""
    _, _, match_id = await _seed_match_infrastructure()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_VIEWER),
        )
        assert res.status_code == 200
        assert res.json() is None


# ==============================================================================
# 30-32. Approved Actuals Filtering and Pagination
# ==============================================================================

@pytest.mark.asyncio
async def test_30_approved_actual_pagination_works():
    """Verify limit and offset pagination on approved actuals endpoint."""
    # Seed 3 approved actuals
    for i in range(3):
        _, _, match_id = await _seed_match_infrastructure(
            activity_code=f"ACT-PAG-{i}",
            activity_name=f"Pagination Activity {i}",
            progress_val=float(10 + i),
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
                headers=auth_header(USER_PLANNER),
                json={},
            )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Page 1: limit=2, offset=0
        res1 = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?limit=2&offset=0",
            headers=auth_header(USER_VIEWER),
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["total"] == 3
        assert len(data1["items"]) == 2
        assert data1["limit"] == 2
        assert data1["offset"] == 0

        # Page 2: limit=2, offset=2
        res2 = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?limit=2&offset=2",
            headers=auth_header(USER_VIEWER),
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["total"] == 3
        assert len(data2["items"]) == 1
        assert data2["limit"] == 2
        assert data2["offset"] == 2


@pytest.mark.asyncio
async def test_31_schedule_activity_id_filter_works():
    """Verify filtering approved actuals by schedule_activity_id."""
    sched_1, _, match_1 = await _seed_match_infrastructure(activity_code="ACT-F-1")
    sched_2, _, match_2 = await _seed_match_infrastructure(activity_code="ACT-F-2")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_1}/approve",
            headers=auth_header(USER_PLANNER),
        )
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_2}/approve",
            headers=auth_header(USER_PLANNER),
        )

        res_filt = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?schedule_activity_id={sched_1}",
            headers=auth_header(USER_VIEWER),
        )
        assert res_filt.status_code == 200
        data = res_filt.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["schedule_activity_id"] == sched_1


@pytest.mark.asyncio
async def test_32_date_filters_work():
    """Verify from_date and to_date filters on approved actuals."""
    sched_id, _, match_id = await _seed_match_infrastructure()

    # Modify with specific date
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/modify",
            headers=auth_header(USER_PLANNER),
            json={
                "schedule_activity_id": sched_id,
                "actual_quantity": 20.0,
                "actual_date": "2026-08-15",
                "notes": "Mid-August milestone",
            },
        )

        # Match in range
        res_in = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?from_date=2026-08-01&to_date=2026-08-31",
            headers=auth_header(USER_VIEWER),
        )
        assert res_in.status_code == 200
        assert res_in.json()["total"] == 1

        # Out of range (future)
        res_out = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals?from_date=2026-09-01&to_date=2026-09-30",
            headers=auth_header(USER_VIEWER),
        )
        assert res_out.status_code == 200
        assert res_out.json()["total"] == 0


# ==============================================================================
# 33-34. Security & Sanitization
# ==============================================================================

@pytest.mark.asyncio
async def test_33_api_errors_contain_no_secrets():
    """Verify error responses do not leak keys, passwords, or credentials."""
    non_existent = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{non_existent}/approve",
            headers=auth_header(USER_PLANNER),
        )
        body = res.text.lower()
        assert "service_role" not in body
        assert "secret" not in body
        assert "password" not in body
        assert "gemini" not in body
        assert "jwt" not in body


@pytest.mark.asyncio
async def test_34_api_errors_contain_no_stack_trace():
    """Verify error responses conform to ApiErrorResponse and contain no stack traces."""
    non_existent = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{non_existent}/approve",
            headers=auth_header(USER_PLANNER),
        )
        data = res.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]
        assert "Traceback" not in res.text
        assert "File \"" not in res.text


# ==============================================================================
# Additional Security Test: Outsider Access Blocked
# ==============================================================================

@pytest.mark.asyncio
async def test_outsider_cannot_access_project_decisions_or_actuals():
    """User not member of Project A cannot approve, reject, modify, read decisions, or read actuals."""
    _, _, match_id = await _seed_match_infrastructure(project_id=PROJECT_A_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST approve
        res1 = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/approve",
            headers=auth_header(USER_OUTSIDER),
        )
        assert res1.status_code == 403

        # POST reject
        res2 = await client.post(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/reject",
            headers=auth_header(USER_OUTSIDER),
            json={"rejection_reason": "Outsider"},
        )
        assert res2.status_code == 403

        # GET decision
        res3 = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/matches/{match_id}/decision",
            headers=auth_header(USER_OUTSIDER),
        )
        assert res3.status_code == 403

        # GET approved-actuals
        res4 = await client.get(
            f"/api/v1/projects/{PROJECT_A_ID}/approved-actuals",
            headers=auth_header(USER_OUTSIDER),
        )
        assert res4.status_code == 403
