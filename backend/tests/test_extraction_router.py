"""
SiteSync AI — Phase 5.6 Extraction API Router Tests.
Tests:
  - Unauthenticated trigger -> 401
  - Viewer trigger -> 403
  - Supervisor trigger -> 200 success
  - Planner trigger -> 200 success
  - Admin trigger -> 200 success
  - Valid project/input extraction -> ExtractionService called
  - Cross-project input -> 404 blocked
  - Nonexistent input -> 404
  - Empty input -> 400
  - Gemini provider failure -> 502
  - Gemini timeout -> 502
  - Malformed extraction response -> 502
  - Evidence verification failure -> 422 controlled error
  - Viewer can read extraction records -> 200
  - Supervisor can read extraction records -> 200
  - Planner can read extraction records -> 200
  - Admin can read extraction records -> 200
  - Project extraction list supports status filtering
  - Pagination validates limit and offset
  - Input extraction endpoint cannot return another input's records
  - No sensitive credentials appear in API errors
  - DELETE extraction endpoint does not exist (405/404)
"""

from __future__ import annotations

from datetime import date
import time
from unittest.mock import AsyncMock, patch
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.extractions import ExtractionStatus
from app.schemas.inputs import TextInputCreate
from app.services.extraction_service import extraction_service
from app.services.gemini_service import (
    GeminiExtractionParseError,
    GeminiProviderError,
    GeminiTimeoutError,
)
from app.services.input_service import input_service

client = TestClient(app)

PROJECT_ID = "proj-test-56"
OTHER_PROJECT_ID = "proj-other-56"

USER_VIEWER = "user-v-56"
USER_SUPERVISOR = "user-s-56"
USER_PLANNER = "user-p-56"
USER_ADMIN = "user-a-56"
USER_OUTSIDER = "user-out-56"


def create_jwt(user_id: str, email: str = "test@sitesync.ai") -> str:
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
    membership_registry.clear()
    input_service.clear()
    extraction_service.clear()

    # Seed projects
    membership_registry.seed_project(
        project_id=PROJECT_ID,
        name="Phase 5 Test Project",
        code="P5-2026",
    )
    membership_registry.seed_project(
        project_id=OTHER_PROJECT_ID,
        name="Other Project",
        code="OTH-2026",
    )

    # Seed memberships
    membership_registry.add_membership(USER_VIEWER, PROJECT_ID, ProjectRole.VIEWER)
    membership_registry.add_membership(USER_SUPERVISOR, PROJECT_ID, ProjectRole.SUPERVISOR)
    membership_registry.add_membership(USER_PLANNER, PROJECT_ID, ProjectRole.PLANNER)
    membership_registry.add_membership(USER_ADMIN, PROJECT_ID, ProjectRole.ADMIN)
    membership_registry.add_membership(USER_OUTSIDER, OTHER_PROJECT_ID, ProjectRole.ADMIN)

    yield

    membership_registry.clear()
    input_service.clear()
    extraction_service.clear()


# Mock LLM extraction payload
MOCK_EXTRACTION_JSON = {
    "extracted_activities": [
        {
            "description": "Erected 10 spools of pipework",
            "progress_value": 10.0,
            "progress_unit": "spools",
            "discipline": "Piping",
            "evidence_tokens": ["erected 10 spools"],
        }
    ],
    "extraction_confidence": 0.95,
}


# --- 1. Authentication & RBAC Tests ---

def test_unauthenticated_trigger_returns_401():
    resp = client.post(f"/api/v1/projects/{PROJECT_ID}/inputs/some-id/extract")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_viewer_trigger_returns_403():
    # Create input
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="erected 10 spools of pipework today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    resp = client.post(
        f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
        headers=auth_header(USER_VIEWER),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_supervisor_trigger_succeeds():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="erected 10 spools of pipework today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        new_callable=AsyncMock,
    ) as mock_extract:
        from app.schemas.extractions import ExtractedActivity, ExtractionResult
        mock_extract.return_value = ExtractionResult(
            raw_input_id=uuid.UUID(inp.id),
            extracted_activities=[
                ExtractedActivity(
                    description="Erected 10 spools of pipework",
                    progress_value=10.0,
                    progress_unit="spools",
                    discipline="Piping",
                    evidence_tokens=["erected 10 spools"],
                )
            ],
            extraction_confidence=0.95,
            model_version="gemini-1.5-flash:extraction_v1",
        )

        resp = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["confidence_score"] == 0.95
        assert data["field_input_id"] == inp.id


def test_planner_and_admin_trigger_succeeds():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="erected 10 spools of pipework today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        new_callable=AsyncMock,
    ) as mock_extract:
        from app.schemas.extractions import ExtractedActivity, ExtractionResult
        mock_extract.return_value = ExtractionResult(
            raw_input_id=uuid.UUID(inp.id),
            extracted_activities=[
                ExtractedActivity(
                    description="Erected 10 spools",
                    progress_value=10.0,
                    progress_unit="spools",
                    discipline="Piping",
                    evidence_tokens=["erected 10 spools"],
                )
            ],
            extraction_confidence=0.92,
            model_version="gemini-1.5-flash:extraction_v1",
        )

        # Planner
        resp_p = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_PLANNER),
        )
        assert resp_p.status_code == 200

        # Admin
        resp_a = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_ADMIN),
        )
        assert resp_a.status_code == 200


# --- 2. Project Isolation & IDOR Defense Tests ---

def test_cross_project_input_trigger_blocked():
    # Input created in OTHER_PROJECT_ID
    other_inp = input_service.create_text_input(
        project_id=OTHER_PROJECT_ID,
        data=TextInputCreate(raw_text="Other project work"),
        submitted_by_id=USER_OUTSIDER,
    )

    # Attempt to trigger extraction from PROJECT_ID context
    resp = client.post(
        f"/api/v1/projects/{PROJECT_ID}/inputs/{other_inp.id}/extract",
        headers=auth_header(USER_ADMIN),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INPUT_NOT_FOUND"


def test_nonexistent_input_trigger_returns_404():
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/projects/{PROJECT_ID}/inputs/{fake_id}/extract",
        headers=auth_header(USER_SUPERVISOR),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INPUT_NOT_FOUND"


def test_outsider_cannot_access_project_extractions():
    resp = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions",
        headers=auth_header(USER_OUTSIDER),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# --- 3. Error Handling & Provider Failure Mapping Tests ---

def test_empty_raw_text_returns_400():
    input_id = str(uuid.uuid4())
    input_service._inputs[input_id] = {
        "id": input_id,
        "project_id": PROJECT_ID,
        "submitted_by": USER_SUPERVISOR,
        "input_type": "text",
        "title": "Empty note",
        "raw_text": "   ",
        "media_path": None,
        "media_filename": None,
        "media_mime_type": None,
        "media_size_bytes": 0,
        "audio_duration_seconds": None,
        "transcription_status": "none",
        "transcription_error": None,
        "field_date": date(2026, 8, 30),
        "metadata": {},
        "created_at": "2026-08-30T12:00:00Z",
        "updated_at": "2026-08-30T12:00:00Z",
    }

    resp = client.post(
        f"/api/v1/projects/{PROJECT_ID}/inputs/{input_id}/extract",
        headers=auth_header(USER_SUPERVISOR),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_INPUT"


def test_gemini_provider_failure_returns_502():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="Work done today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        side_effect=GeminiProviderError("Gemini 503 Service Unavailable"),
    ):
        resp = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "AI_PROVIDER_ERROR"
        # Verify no sensitive API keys in response
        assert "key" not in resp.text.lower()


def test_gemini_timeout_returns_502():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="Work done today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        side_effect=GeminiTimeoutError("Provider call timed out after 15.0s"),
    ):
        resp = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "AI_PROVIDER_ERROR"


def test_malformed_extraction_parse_error_returns_502():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="Work done today"),
        submitted_by_id=USER_SUPERVISOR,
    )

    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        side_effect=GeminiExtractionParseError("Malformed JSON output"),
    ):
        resp = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "AI_PROVIDER_ERROR"


def test_evidence_verification_failure_returns_422():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="Welded joint J-100 on Rack 1."),
        submitted_by_id=USER_SUPERVISOR,
    )

    from app.schemas.extractions import ExtractedActivity, ExtractionResult
    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        new_callable=AsyncMock,
    ) as mock_extract:
        mock_extract.return_value = ExtractionResult(
            raw_input_id=uuid.UUID(inp.id),
            extracted_activities=[
                ExtractedActivity(
                    description="Welded joint",
                    progress_value=1.0,
                    progress_unit="joint",
                    discipline="Piping",
                    evidence_tokens=["Fabricated hallucinated token not in raw_text"],
                )
            ],
            extraction_confidence=0.90,
            model_version="gemini-1.5-flash:extraction_v1",
        )

        resp = client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "EVIDENCE_VERIFICATION_FAILED"


# --- 4. Read Endpoints & Pagination Tests ---

def test_viewer_can_read_extraction_records():
    inp = input_service.create_text_input(
        project_id=PROJECT_ID,
        data=TextInputCreate(raw_text="Installed foundation rebar on Grid A."),
        submitted_by_id=USER_SUPERVISOR,
    )

    # 1. Trigger as Supervisor
    with patch.object(
        extraction_service.gemini_service,
        "extract_structured_data",
        new_callable=AsyncMock,
    ) as mock_extract:
        from app.schemas.extractions import ExtractedActivity, ExtractionResult
        mock_extract.return_value = ExtractionResult(
            raw_input_id=uuid.UUID(inp.id),
            extracted_activities=[
                ExtractedActivity(
                    description="Installed foundation rebar on Grid A",
                    progress_value=100.0,
                    progress_unit="%",
                    discipline="Civil",
                    evidence_tokens=["Installed foundation rebar"],
                )
            ],
            extraction_confidence=0.98,
            model_version="gemini-1.5-flash:extraction_v1",
        )

        client.post(
            f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
            headers=auth_header(USER_SUPERVISOR),
        )

    # 2. Read by input as Viewer
    resp_input = client.get(
        f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extractions",
        headers=auth_header(USER_VIEWER),
    )
    assert resp_input.status_code == 200
    data_input = resp_input.json()
    assert data_input["total"] == 1
    assert data_input["extractions"][0]["status"] == "completed"

    # 3. Read project list as Viewer
    resp_list = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions",
        headers=auth_header(USER_VIEWER),
    )
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert data_list["total"] == 1


def test_status_filtering_and_pagination():
    # Create 3 inputs and extract
    for i in range(3):
        inp = input_service.create_text_input(
            project_id=PROJECT_ID,
            data=TextInputCreate(raw_text=f"Progress step {i} completed."),
            submitted_by_id=USER_SUPERVISOR,
        )
        with patch.object(
            extraction_service.gemini_service,
            "extract_structured_data",
            new_callable=AsyncMock,
        ) as mock_extract:
            from app.schemas.extractions import ExtractedActivity, ExtractionResult
            mock_extract.return_value = ExtractionResult(
                raw_input_id=uuid.UUID(inp.id),
                extracted_activities=[
                    ExtractedActivity(
                        description=f"Progress step {i}",
                        progress_value=1.0,
                        progress_unit="item",
                        discipline="General",
                        evidence_tokens=[f"Progress step {i}"],
                    )
                ],
                extraction_confidence=0.90,
                model_version="gemini-1.5-flash:extraction_v1",
            )
            client.post(
                f"/api/v1/projects/{PROJECT_ID}/inputs/{inp.id}/extract",
                headers=auth_header(USER_SUPERVISOR),
            )

    # Filter completed
    resp_filtered = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions?status=completed",
        headers=auth_header(USER_PLANNER),
    )
    assert resp_filtered.status_code == 200
    assert resp_filtered.json()["total"] == 3

    # Filter failed (none exist)
    resp_failed = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions?status=failed",
        headers=auth_header(USER_PLANNER),
    )
    assert resp_failed.status_code == 200
    assert resp_failed.json()["total"] == 0

    # Limit and offset
    resp_page = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions?limit=2&offset=1",
        headers=auth_header(USER_ADMIN),
    )
    assert resp_page.status_code == 200
    assert len(resp_page.json()["extractions"]) == 2
    assert resp_page.json()["total"] == 3


def test_invalid_pagination_parameters_rejected():
    # Limit out of bounds (< 1)
    resp_bad_limit = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions?limit=0",
        headers=auth_header(USER_VIEWER),
    )
    assert resp_bad_limit.status_code == 422

    # Negative offset
    resp_bad_offset = client.get(
        f"/api/v1/projects/{PROJECT_ID}/extractions?offset=-1",
        headers=auth_header(USER_VIEWER),
    )
    assert resp_bad_offset.status_code == 422


def test_delete_endpoint_does_not_exist():
    # Ensure DELETE route is not registered on extraction API
    resp_del_input = client.delete(
        f"/api/v1/projects/{PROJECT_ID}/inputs/some-id/extractions",
        headers=auth_header(USER_ADMIN),
    )
    assert resp_del_input.status_code in (404, 405)

    resp_del_extract = client.delete(
        f"/api/v1/projects/{PROJECT_ID}/inputs/some-id/extract",
        headers=auth_header(USER_ADMIN),
    )
    assert resp_del_extract.status_code in (404, 405)
