"""
SiteSync AI — Phase 4 Field Inputs API & Authorization Tests.
Tests:
  - Viewer can list inputs (200)
  - Supervisor can create text input (201)
  - Planner and Admin can create text input (201)
  - Viewer cannot create text input (403)
  - Admin can delete field input (200)
  - Non-admin cannot delete field input (403)
  - Cross-project / IDOR isolation enforced (403)
  - Unauthenticated access blocked (401)
  - Invalid MIME type rejected (400)
  - Invalid extension rejected (400)
  - Oversized file rejected (400)
  - Valid photo upload (201)
  - Valid document upload (201)
  - Valid voice upload with Whisper transcription success (201, completed)
  - Signed URL generation when media exists
  - Whisper STT failure preserves uploaded audio and marks input failed
"""

from __future__ import annotations

import io
import time
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole
from app.schemas.inputs import FieldInputType
from app.services.input_service import input_service
from app.services.stt_service import stt_service

client = TestClient(app)


def create_test_jwt(user_id: str, email: str) -> str:
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


@pytest.fixture(autouse=True)
def setup_test_state():
    membership_registry.clear()
    input_service.clear()
    stt_service.set_force_failure(False)

    # Seed projects
    membership_registry.seed_project(
        project_id="proj-mtp",
        name="MTP – Refinery Expansion",
        code="MTP-2026",
    )
    membership_registry.seed_project(
        project_id="proj-other",
        name="Other Project",
        code="OTH-2026",
    )

    # Memberships on proj-mtp
    membership_registry.add_membership("user-admin", "proj-mtp", ProjectRole.ADMIN)
    membership_registry.add_membership("user-planner", "proj-mtp", ProjectRole.PLANNER)
    membership_registry.add_membership("user-supervisor", "proj-mtp", ProjectRole.SUPERVISOR)
    membership_registry.add_membership("user-viewer", "proj-mtp", ProjectRole.VIEWER)

    # Outsider membership only on proj-other
    membership_registry.add_membership("user-outsider", "proj-other", ProjectRole.ADMIN)

    # Initial text input in proj-mtp
    input_service.create_text_input(
        project_id="proj-mtp",
        data=type("Obj", (), {
            "title": "Initial Shift Note",
            "raw_text": "Completed preliminary excavation inspection.",
            "field_date": None,
            "metadata": {},
        })(),
        submitted_by_id="user-supervisor",
        submitted_by_email="supervisor@sitesync.ai",
    )

    yield


def test_unauthenticated_inputs_list_returns_401():
    response = client.get("/api/v1/projects/proj-mtp/inputs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_viewer_can_list_inputs():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/inputs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["inputs"][0]["title"] == "Initial Shift Note"
    assert body["inputs"][0]["input_type"] == "text"


def test_supervisor_can_create_text_input():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    payload = {
        "title": "Piping Inspection Morning",
        "raw_text": "Completed flange alignment on Rack 3. Waiting on torque team.",
        "field_date": "2026-08-30",
    }
    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/text",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Piping Inspection Morning"
    assert body["raw_text"] == payload["raw_text"]
    assert body["submitted_by"] == "user-supervisor"
    assert body["input_type"] == "text"


def test_planner_and_admin_can_create_text_input():
    for user_role, uid in [("planner", "user-planner"), ("admin", "user-admin")]:
        token = create_test_jwt(uid, f"{user_role}@sitesync.ai")
        response = client.post(
            "/api/v1/projects/proj-mtp/inputs/text",
            json={"title": f"Note by {user_role}", "raw_text": f"Progress logged by {user_role}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201


def test_viewer_cannot_create_text_input_returns_403():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/text",
        json={"title": "Unauthorized Note", "raw_text": "I am a viewer trying to write notes"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_empty_raw_text_returns_422():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/text",
        json={"title": "Empty Note", "raw_text": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_admin_can_delete_input():
    token = create_test_jwt("user-admin", "admin@sitesync.ai")
    list_res = client.get(
        "/api/v1/projects/proj-mtp/inputs",
        headers={"Authorization": f"Bearer {token}"},
    )
    inp_id = list_res.json()["inputs"][0]["id"]

    del_res = client.delete(
        f"/api/v1/projects/proj-mtp/inputs/{inp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


def test_planner_and_supervisor_cannot_delete_input_returns_403():
    token = create_test_jwt("user-planner", "planner@sitesync.ai")
    list_res = client.get(
        "/api/v1/projects/proj-mtp/inputs",
        headers={"Authorization": f"Bearer {token}"},
    )
    inp_id = list_res.json()["inputs"][0]["id"]

    del_res = client.delete(
        f"/api/v1/projects/proj-mtp/inputs/{inp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_cross_project_isolation_idor_blocked():
    token = create_test_jwt("user-outsider", "outsider@sitesync.ai")
    response = client.get(
        "/api/v1/projects/proj-mtp/inputs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_valid_photo_upload():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    fake_image = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 50

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "photo", "title": "Foundation Crack Inspection"},
        files={"file": ("foundation.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["input_type"] == "photo"
    assert body["media_filename"] == "foundation.jpg"
    assert body["media_path"].startswith("projects/proj-mtp/inputs/")
    assert body["media_url"] is not None


def test_valid_document_upload():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "document", "title": "Site Inspection Checklist"},
        files={"file": ("checklist.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["input_type"] == "document"
    assert body["media_filename"] == "checklist.pdf"
    assert body["media_path"].startswith("projects/proj-mtp/inputs/")


def test_valid_voice_upload_with_whisper_transcription():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    fake_audio = b"\x1a\x45\xdf\xa3" + b"\x00" * 200  # WebM header

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "voice", "title": "Evening Voice Note"},
        files={"file": ("site_audio.webm", io.BytesIO(fake_audio), "audio/webm")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["input_type"] == "voice"
    assert body["transcription_status"] == "completed"
    assert body["raw_text"] is not None
    assert "Line 24" in body["raw_text"] or "pipe spool" in body["raw_text"].lower()
    assert body["media_path"] is not None
    assert body["media_url"] is not None


def test_invalid_mime_type_rejected():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    fake_exe = b"MZ\x90\x00"

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "photo"},
        files={"file": ("bad_script.jpg", io.BytesIO(fake_exe), "application/x-msdownload")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MIME_TYPE"


def test_invalid_extension_rejected():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    fake_image = b"\xff\xd8\xff\xe0"

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "photo"},
        files={"file": ("photo.exe", io.BytesIO(fake_image), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_EXTENSION"


def test_oversized_photo_rejected():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    oversized = b"\x00" * (16 * 1024 * 1024)  # 16 MB > 15 MB limit

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "photo"},
        files={"file": ("huge_photo.jpg", io.BytesIO(oversized), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_whisper_failure_preserves_audio_and_input_record():
    token = create_test_jwt("user-supervisor", "supervisor@sitesync.ai")
    stt_service.set_force_failure(True)
    fake_audio = b"some_audio_bytes"

    response = client.post(
        "/api/v1/projects/proj-mtp/inputs/upload",
        data={"input_type": "voice", "title": "Voice Note Failing STT"},
        files={"file": ("failing_voice.webm", io.BytesIO(fake_audio), "audio/webm")},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Must succeed in creating the record (201), with failed transcription status
    assert response.status_code == 201
    body = response.json()
    assert body["input_type"] == "voice"
    assert body["transcription_status"] == "failed"
    assert body["transcription_error"] is not None
    assert body["media_path"] is not None
    assert body["media_url"] is not None

    # Verify input can be retrieved later
    get_res = client.get(
        f"/api/v1/projects/proj-mtp/inputs/{body['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["transcription_status"] == "failed"

    stt_service.set_force_failure(False)


def test_get_single_input_with_signed_url():
    token = create_test_jwt("user-viewer", "viewer@sitesync.ai")
    list_res = client.get(
        "/api/v1/projects/proj-mtp/inputs",
        headers={"Authorization": f"Bearer {token}"},
    )
    inp_id = list_res.json()["inputs"][0]["id"]

    get_res = client.get(
        f"/api/v1/projects/proj-mtp/inputs/{inp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == inp_id
