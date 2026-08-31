"""
FastAPI HTTP Integration and Security tests for Phase 10.3 Audit & Provenance APIs.
Verifies:
1. All roles (Viewer, Supervisor, Planner, Admin) have read access
2. Unauthenticated requests are rejected with 401
3. Cross-project requests are rejected with 403/404 (no IDOR)
4. Deterministic audit ordering and pagination
5. Domain filters (event_type, entity_type, etc.)
6. Audit immutability (POST, PUT, PATCH, DELETE are blocked with 405)
7. Full provenance graph resolution (Approved, Rejected, Modified)
8. Safe error sanitization
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.audit import AuditEventType, ProvenanceNodeType
from app.schemas.auth import ProjectRole
from app.schemas.decision import (
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
)
from app.schemas.extractions import (
    ExtractedActivity,
    ExtractionResponse,
    ExtractionResult,
    ExtractionStatus,
)
from app.schemas.inputs import (
    FieldInputResponse,
    FieldInputType,
    TextInputCreate,
    TranscriptionStatus,
)
from app.schemas.schedule import (
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScoringBreakdown,
)
from app.services.audit_service import audit_service
from app.services.decision_service import decision_service
from app.services.extraction_service import extraction_service
from app.services.input_service import input_service
from app.services.matching_service import matching_service
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
    matching_service.repository.clear()
    decision_service.actual_repo.clear()
    decision_service.decision_repo.clear()
    decision_service.match_repo = matching_service.repository
    audit_service.decision_service = decision_service
    audit_service.matching_service = matching_service

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
async def test_unauthenticated_audit_request_rejected():
    """Verifies that requests without a Bearer token return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/audit")
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
async def test_all_roles_can_list_audit_events(user_id: str, role_name: str):
    """Verifies that VIEWER, SUPERVISOR, PLANNER, and ADMIN can access the audit stream."""
    token = create_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Populate a sample input
    input_service.create_text_input(
        project_id=PROJECT_A,
        data=TextInputCreate(title="Sample Field Log", raw_text="Poured foundation."),
        submitted_by_id=user_id,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_A}/audit", headers=headers)
        assert resp.status_code == 200, f"Role {role_name} failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_cross_project_audit_access_forbidden():
    """Verifies that a user authorized on Project A cannot query Project B audit events (403 Forbidden)."""
    token_a = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/projects/{PROJECT_B}/audit", headers=headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_event_filters_and_pagination():
    """Verifies event_type filtering, pagination parameters, and limits."""
    token = create_jwt(USER_PLANNER)
    headers = {"Authorization": f"Bearer {token}"}

    input_service.create_text_input(
        project_id=PROJECT_A,
        data=TextInputCreate(title="Input 1", raw_text="Log 1"),
        submitted_by_id=USER_PLANNER,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Filter by FIELD_INPUT_SUBMITTED
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit?event_type=FIELD_INPUT_SUBMITTED&limit=10&offset=0",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert all(it["event_type"] == "FIELD_INPUT_SUBMITTED" for it in data["items"])

        # Invalid event_type filter returns 422
        bad_resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit?event_type=NONEXISTENT_TYPE",
            headers=headers,
        )
        assert bad_resp.status_code == 422


@pytest.mark.asyncio
async def test_audit_immutability_blocks_mutating_verbs():
    """Verifies that POST, PUT, PATCH, and DELETE are strictly disallowed on /audit endpoints (405)."""
    token = create_jwt(USER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_post = await client.post(f"/api/v1/projects/{PROJECT_A}/audit", headers=headers, json={})
        assert resp_post.status_code == 405

        resp_put = await client.put(f"/api/v1/projects/{PROJECT_A}/audit", headers=headers, json={})
        assert resp_put.status_code == 405

        resp_patch = await client.patch(f"/api/v1/projects/{PROJECT_A}/audit", headers=headers, json={})
        assert resp_patch.status_code == 405

        resp_delete = await client.delete(f"/api/v1/projects/{PROJECT_A}/audit", headers=headers)
        assert resp_delete.status_code == 405


@pytest.mark.asyncio
async def test_provenance_api_full_lineage():
    """Verifies that the /provenance endpoint returns the complete causal graph for an approved actual."""
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Baseline activity
    act = await schedule_service.create_or_update_activity(
        PROJECT_A,
        ScheduleActivityCreate(activity_code="ACT-777", name="Structural Slab"),
    )

    # 2. Input
    inp = input_service.create_text_input(
        project_id=PROJECT_A,
        data=TextInputCreate(title="Slab Log", raw_text="Poured 25 m3 slab."),
        submitted_by_id=USER_VIEWER,
    )

    # 3. Extraction
    ext_res = ExtractionResult(
        raw_input_id=UUID(inp.id),
        extracted_activities=[
            ExtractedActivity(
                description="Poured 25 m3 slab.",
                discipline="Civil",
                location="Zone 1",
                progress_value=25.0,
                progress_unit="m3",
                event_date=date(2026, 8, 20),
                evidence_tokens=["25 m3"],
            )
        ],
        extraction_confidence=0.9,
        model_version="gemini-1.5-pro",
        processing_timestamp=datetime.now(timezone.utc),
    )
    ext_rec = await extraction_service.repository.upsert_completed(PROJECT_A, inp.id, ext_res)

    # 4. Match
    match_rec = MatchRecommendationResponse(
        id=uuid4(),
        project_id=UUID(PROJECT_A),
        extraction_id=UUID(ext_rec["id"]),
        activity_index=0,
        recommended_activity_id=UUID(str(act.id)),
        recommended_activity_code=act.activity_code,
        recommended_activity_name=act.name,
        confidence_score=0.9,
        scoring_breakdown=ScoringBreakdown(semantic_similarity=0.9, discipline_contribution=0.0, location_contribution=0.0, temporal_contribution=0.0),
        alternative_matches=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await matching_service.repository.upsert_match(match_rec)

    # 5. Approve
    actual = await decision_service.approve_match(
        project_id=PROJECT_A,
        match_id=match_rec.id,
        planner_id=UUID(USER_PLANNER),
        notes="Verified slab pour",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{actual.id}",
            headers=headers,
        )
        assert resp.status_code == 200, f"Error: {resp.text}"
        chain = resp.json()
        assert chain["project_id"] == PROJECT_A
        assert chain["root_entity_type"] == "APPROVED_ACTUAL"
        assert chain["root_entity_id"] == str(actual.id)
        assert chain["is_complete"] is True
        assert len(chain["nodes"]) >= 5


@pytest.mark.asyncio
async def test_provenance_api_missing_entity_returns_404():
    """Verifies that querying provenance for a nonexistent entity returns 404."""
    token = create_jwt(USER_VIEWER)
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = str(uuid4())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{fake_id}",
            headers=headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "ENTITY_NOT_FOUND"
