"""
SiteSync AI — Phase 2 Authentication & Server-Side Authorization Tests.
Tests:
  - JWT token verification and decoding
  - Rejection of unauthenticated requests (401)
  - Rejection of expired/malformed tokens (401)
  - Server-side identity resolution (JWT claims only)
  - Authorized project access (200)
  - Prevention of unauthorized cross-project access / IDOR (403)
  - Role hierarchy and admin permission enforcement (403 for non-admin)
"""

from __future__ import annotations

import time
import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import membership_registry
from app.main import app
from app.schemas.auth import ProjectRole

client = TestClient(app)


def create_test_jwt(
    user_id: str,
    email: str,
    expires_in_seconds: int = 3600,
    full_name: str | None = None,
) -> str:
    """Helper to generate test Supabase Auth JWTs."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in_seconds,
        "user_metadata": {"full_name": full_name} if full_name else {},
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_test_registry():
    """Setup clean project memberships before each test."""
    membership_registry.clear()

    # Seed test projects
    membership_registry.seed_project(
        project_id="proj-alpha",
        name="Project Alpha",
        code="ALPHA-01",
        description="Alpha Test Site",
    )
    membership_registry.seed_project(
        project_id="proj-beta",
        name="Project Beta",
        code="BETA-02",
        description="Beta Test Site",
    )

    # Seed user memberships
    # Alice is admin on Alpha, viewer on Beta
    membership_registry.add_membership(
        user_id="user-alice",
        project_id="proj-alpha",
        role=ProjectRole.ADMIN,
    )
    membership_registry.add_membership(
        user_id="user-alice",
        project_id="proj-beta",
        role=ProjectRole.VIEWER,
    )

    # Bob is only on Beta as planner
    membership_registry.add_membership(
        user_id="user-bob",
        project_id="proj-beta",
        role=ProjectRole.PLANNER,
    )

    yield


# ── 1. Unauthenticated / Malformed Requests ───────────────────────────────────

def test_unauthenticated_request_to_me_returns_401():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_malformed_token_returns_401():
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.malformed.token"},
    )
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_expired_token_returns_401():
    expired_token = create_test_jwt("user-alice", "alice@example.com", expires_in_seconds=-10)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "TOKEN_EXPIRED"


# ── 2. Authenticated Identity Resolution ─────────────────────────────────────

def test_valid_token_resolves_user_and_memberships():
    token = create_test_jwt("user-alice", "alice@example.com", full_name="Alice Architect")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "user-alice"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["full_name"] == "Alice Architect"
    assert len(body["memberships"]) == 2

    project_ids = {m["project_id"] for m in body["memberships"]}
    assert "proj-alpha" in project_ids
    assert "proj-beta" in project_ids


# ── 3. Server-Side Project Authorization & IDOR Prevention ────────────────────

def test_authorized_user_can_access_own_project():
    token = create_test_jwt("user-bob", "bob@example.com")
    response = client.get(
        "/api/v1/projects/proj-beta",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "proj-beta"
    assert body["code"] == "BETA-02"
    assert body["user_role"] == "planner"


def test_unauthorized_user_cannot_access_other_project_idor_blocked():
    # Bob is NOT a member of proj-alpha
    token = create_test_jwt("user-bob", "bob@example.com")
    response = client.get(
        "/api/v1/projects/proj-alpha",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "FORBIDDEN"


def test_nonexistent_project_returns_404():
    token = create_test_jwt("user-alice", "alice@example.com")
    response = client.get(
        "/api/v1/projects/proj-nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"


# ── 4. Role Hierarchy & Permission Enforcement ────────────────────────────────

def test_admin_can_perform_admin_action():
    # Alice is ADMIN on proj-alpha
    token = create_test_jwt("user-alice", "alice@example.com")
    response = client.post(
        "/api/v1/projects/proj-alpha/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_non_admin_cannot_perform_admin_action():
    # Bob is PLANNER on proj-beta (not ADMIN)
    token = create_test_jwt("user-bob", "bob@example.com")
    response = client.post(
        "/api/v1/projects/proj-beta/admin-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
