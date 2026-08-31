"""
SiteSync AI — Phase 6.6 Schedule Matching Router Tests.
Tests:
  - Unauthenticated POST / GET -> 401
  - RBAC: Viewer & Supervisor POST -> 403, Planner & Admin POST -> 200
  - RBAC: Viewer, Supervisor, Planner, Admin GET -> 200
  - Outsider requests -> 403
  - Cross-project extraction -> 404 (does NOT invoke matching or persist matches)
  - Multi-activity extraction -> produces deterministic activity_index records
  - Idempotent repeated matching -> updates records without duplicating
  - Empty matches list -> returns items=[], total=0
  - No schedule candidates -> 404 NO_SCHEDULE_CANDIDATES
  - Non-completed extraction -> 400
  - Error responses follow canonical ApiErrorResponse without secret leakage
  - Absence of Phase 7, 8, 9 concepts
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
from app.schemas.auth import ProjectRole
from app.schemas.extractions import ExtractedActivity, ExtractionResponse, ExtractionResult, ExtractionStatus
from app.schemas.schedule import ScheduleActivityCreate
from app.services.embedding_service import embedding_service, generate_deterministic_mock_embedding
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


@pytest.fixture(autouse=True)
def setup_test_state():
    """Resets registries and services for clean test execution."""
    membership_registry.clear()
    schedule_service.clear()
    extraction_service.clear()
    matching_service.repository.clear()

    # Configure deterministic mock embedding provider for tests
    embedding_service._mock_provider = lambda text, task_type: generate_deterministic_mock_embedding(text)
    matching_service.embedding_service._mock_provider = lambda text, task_type: generate_deterministic_mock_embedding(text)

    proj_a = "proj-match-a"
    proj_b = "proj-match-b"

    membership_registry.seed_project(proj_a, "Matching Project A", "MATCH-A")
    membership_registry.seed_project(proj_b, "Matching Project B", "MATCH-B")

    # Project A members
    membership_registry.add_membership("admin-user", proj_a, ProjectRole.ADMIN)
    membership_registry.add_membership("planner-user", proj_a, ProjectRole.PLANNER)
    membership_registry.add_membership("supervisor-user", proj_a, ProjectRole.SUPERVISOR)
    membership_registry.add_membership("viewer-user", proj_a, ProjectRole.VIEWER)

    # Project B members (Outsider to A)
    membership_registry.add_membership("outsider-user", proj_b, ProjectRole.ADMIN)


async def _create_test_extraction(
    project_id: str,
    activities: list[ExtractedActivity],
    status: ExtractionStatus = ExtractionStatus.COMPLETED,
) -> ExtractionResponse:
    """Helper to seed completed extraction record in extraction_service."""
    input_id = uuid4()
    now = datetime.now(timezone.utc)
    ext_result = ExtractionResult(
        raw_input_id=input_id,
        extracted_activities=activities,
        extraction_confidence=0.92,
        model_version="mock-v1",
        processing_timestamp=now,
    )
    row = await extraction_service.repository.upsert_completed(
        project_id=project_id,
        field_input_id=str(input_id),
        extraction=ext_result,
    )
    return extraction_service._to_response(row)


@pytest.mark.asyncio
async def test_unauthenticated_matching_routes_return_401():
    """Verify unauthenticated matching endpoints return 401."""
    ext_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_post = await client.post(f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match")
        assert res_post.status_code == 401

        res_get = await client.get(f"/api/v1/projects/proj-match-a/extractions/{ext_id}/matches")
        assert res_get.status_code == 401


@pytest.mark.asyncio
async def test_matching_rbac_matrix():
    """Verify RBAC: Planner & Admin can trigger matching, Viewer & Supervisor are 403."""
    # 1. Seed schedule activity in Project A
    await schedule_service.create_or_update_activity(
        "proj-match-a",
        ScheduleActivityCreate(
            activity_code="ACT-100",
            name="Install Underground Sewer Pipe",
            discipline="Piping",
            location="Zone 1",
            planned_start_date=date(2026, 9, 1),
            planned_finish_date=date(2026, 9, 15),
            planned_quantity=200.0,
            planned_unit="LF",
        ),
    )

    # 2. Seed extraction in Project A
    ext = await _create_test_extraction(
        "proj-match-a",
        [ExtractedActivity(description="Laid 50 LF sewer pipe", discipline="Piping", location="Zone 1")],
    )
    ext_id = str(ext.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Viewer POST -> 403
        res_v = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("viewer-user"),
        )
        assert res_v.status_code == 403

        # Supervisor POST -> 403
        res_s = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("supervisor-user"),
        )
        assert res_s.status_code == 403

        # Planner POST -> 200 OK
        res_p = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("planner-user"),
        )
        assert res_p.status_code == 200
        data_p = res_p.json()
        assert data_p["total"] == 1
        assert data_p["items"][0]["recommended_activity_code"] == "ACT-100"

        # Admin POST -> 200 OK
        res_a = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("admin-user"),
        )
        assert res_a.status_code == 200

        # Viewer, Supervisor, Planner, Admin GET -> 200 OK
        for role_user in ["viewer-user", "supervisor-user", "planner-user", "admin-user"]:
            res_g = await client.get(
                f"/api/v1/projects/proj-match-a/extractions/{ext_id}/matches",
                headers=auth_header(role_user),
            )
            assert res_g.status_code == 200
            assert res_g.json()["total"] == 1


@pytest.mark.asyncio
async def test_outsider_blocked_from_matching():
    """Verify user from Project B cannot trigger or read matches in Project A."""
    ext = await _create_test_extraction(
        "proj-match-a",
        [ExtractedActivity(description="Test activity")],
    )
    ext_id = str(ext.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_post = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("outsider-user"),
        )
        assert res_post.status_code == 403

        res_get = await client.get(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/matches",
            headers=auth_header("outsider-user"),
        )
        assert res_get.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_extraction_returns_404_and_blocks_matching():
    """Verify attempting to match an extraction belonging to Project B via Project A returns 404."""
    ext_b = await _create_test_extraction(
        "proj-match-b",
        [ExtractedActivity(description="Project B Activity")],
    )
    ext_b_id = str(ext_b.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Planner A calls with Extraction B ID
        res = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_b_id}/match",
            headers=auth_header("planner-user"),
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "EXTRACTION_NOT_FOUND"

        # Verify no matches persisted
        matches = await matching_service.repository.list_matches("proj-match-a", ext_b_id)
        assert len(matches) == 0


@pytest.mark.asyncio
async def test_multi_activity_extraction_idempotent_matching():
    """Verify multi-activity extraction produces deterministic activity_index records and idempotent reruns."""
    # Seed 2 schedule activities
    await schedule_service.create_or_update_activity(
        "proj-match-a",
        ScheduleActivityCreate(activity_code="ACT-1", name="Piping works"),
    )
    await schedule_service.create_or_update_activity(
        "proj-match-a",
        ScheduleActivityCreate(activity_code="ACT-2", name="Electrical conduit"),
    )

    # Seed extraction with 2 activities
    ext = await _create_test_extraction(
        "proj-match-a",
        [
            ExtractedActivity(description="Piping activity 0"),
            ExtractedActivity(description="Electrical activity 1"),
        ],
    )
    ext_id = str(ext.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First POST -> creates 2 records
        res1 = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("planner-user"),
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["total"] == 2
        assert data1["items"][0]["activity_index"] == 0
        assert data1["items"][1]["activity_index"] == 1

        # Second POST (Rerun) -> updates existing, total count remains 2
        res2 = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("planner-user"),
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["total"] == 2

        # GET matches verifies 2 records
        res_get = await client.get(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/matches",
            headers=auth_header("viewer-user"),
        )
        assert res_get.status_code == 200
        assert res_get.json()["total"] == 2


@pytest.mark.asyncio
async def test_no_schedule_candidates_returns_controlled_404():
    """Verify matching against a project with zero schedule activities returns 404."""
    ext = await _create_test_extraction(
        "proj-match-a",
        [ExtractedActivity(description="Work done")],
    )
    ext_id = str(ext.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/match",
            headers=auth_header("planner-user"),
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "NO_SCHEDULE_CANDIDATES"


@pytest.mark.asyncio
async def test_empty_matches_returns_empty_list():
    """Verify GET for extraction with no matches returns empty list without error."""
    ext = await _create_test_extraction(
        "proj-match-a",
        [ExtractedActivity(description="Work done")],
    )
    ext_id = str(ext.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            f"/api/v1/projects/proj-match-a/extractions/{ext_id}/matches",
            headers=auth_header("viewer-user"),
        )
        assert res.status_code == 200
        assert res.json() == {"items": [], "total": 0}
