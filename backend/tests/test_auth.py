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


def test_forged_token_with_unrelated_secret_returns_401():
    """Regression test: forged JWT signed with an unrelated secret must be rejected."""
    now = int(time.time())
    payload = {
        "sub": "forged-user-attacker-12345",
        "email": "forged@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    forged_token = jwt.encode(payload, "completely-wrong-secret-key", algorithm="HS256")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_authenticated_user_without_memberships_returns_empty_list():
    """Authenticated user without project memberships receives empty list (no auto-enrollment)."""
    token = create_test_jwt("user-unassigned", "unassigned@example.com")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "user-unassigned"
    assert body["memberships"] == []


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


def test_explicit_email_membership_resolves_correctly():
    # Test user identified by email
    membership_registry.add_membership(
        user_id="architect@sitesync.io",
        project_id="proj-alpha",
        role=ProjectRole.SUPERVISOR,
    )
    token = create_test_jwt("user-custom-uuid-999", "architect@sitesync.io")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["memberships"]) == 1
    assert body["memberships"][0]["project_id"] == "proj-alpha"
    assert body["memberships"][0]["role"] == "supervisor"


# ── 5. Security & Adversarial Regression Tests ─────────────────────────────

def test_alg_none_token_rejected_with_401():
    """Token with alg=none must be rejected with 401."""
    now = int(time.time())
    payload = {
        "sub": "user-alice",
        "email": "alice@example.com",
        "exp": now + 3600,
    }
    # Create token with alg=none
    none_token = jwt.encode(payload, key="", algorithm="none")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {none_token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_unsupported_algorithm_rejected_with_401():
    """Token signed with unsupported algorithm (e.g. HS512) must be rejected with 401."""
    now = int(time.time())
    payload = {
        "sub": "user-alice",
        "email": "alice@example.com",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, "test-secret", algorithm="HS512")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_missing_sub_claim_rejected_with_401():
    """Token missing the 'sub' claim must be rejected with 401."""
    now = int(time.time())
    payload = {
        "email": "alice@example.com",
        "exp": now + 3600,
    }
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_TOKEN"


def test_authorized_supabase_uuid_success():
    """Valid token with explicitly registered user UUID receives authorization."""
    user_uuid = "ae939aff-00f3-4492-a91f-d68963075e2f"
    membership_registry.add_membership(
        user_id=user_uuid,
        project_id="proj-alpha",
        role=ProjectRole.PLANNER,
    )
    token = create_test_jwt(user_uuid, "sanjaydudka70@gmail.com")
    response = client.get(
        "/api/v1/projects/proj-alpha",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "proj-alpha"


def test_unregistered_email_cannot_grant_access():
    """Arbitrary email claim not registered in membership_registry receives no access."""
    token = create_test_jwt("unknown-uuid-123", "attacker@evil.com")
    response = client.get(
        "/api/v1/projects/proj-alpha",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_test_secret_rejected_in_production(monkeypatch):
    """In production mode (app_env != development), test-secret signed tokens must be rejected."""
    from app.core.config import get_settings
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "real-prod-jwt-secret-key-12345")
    get_settings.cache_clear()

    try:
        # Token signed with test-secret
        token = jwt.encode({"sub": "user-alice", "exp": int(time.time()) + 3600}, "test-secret", algorithm="HS256")
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()


def test_production_issuer_validation(monkeypatch):
    """
    In production mode (app_env=production) with SUPABASE_URL configured:
    - Missing iss -> 401 INVALID_TOKEN
    - Incorrect iss -> 401 INVALID_TOKEN
    - Valid iss -> 200 OK (when signed with real secret)
    """
    from app.core.config import get_settings
    prod_secret = "real-prod-jwt-secret-key-123456789"
    supabase_url = "https://qwxsggfqujuyswpkeayj.supabase.co"
    valid_iss = f"{supabase_url}/auth/v1"

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", prod_secret)
    get_settings.cache_clear()

    try:
        now = int(time.time())
        # 1. Missing iss
        t_missing_iss = jwt.encode({"sub": "user-alice", "email": "alice@example.com", "exp": now + 3600}, prod_secret, algorithm="HS256")
        res1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t_missing_iss}"})
        assert res1.status_code == 401
        assert res1.json()["error"]["code"] == "INVALID_TOKEN"

        # 2. Incorrect iss
        t_wrong_iss = jwt.encode({"sub": "user-alice", "email": "alice@example.com", "iss": "https://evil.attacker.com/auth/v1", "exp": now + 3600}, prod_secret, algorithm="HS256")
        res2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t_wrong_iss}"})
        assert res2.status_code == 401
        assert res2.json()["error"]["code"] == "INVALID_TOKEN"

        # 3. Valid iss
        t_valid_iss = jwt.encode({"sub": "user-alice", "email": "alice@example.com", "iss": valid_iss, "exp": now + 3600}, prod_secret, algorithm="HS256")
        res3 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t_valid_iss}"})
        assert res3.status_code == 200
        assert res3.json()["user"]["id"] == "user-alice"
    finally:
        get_settings.cache_clear()
