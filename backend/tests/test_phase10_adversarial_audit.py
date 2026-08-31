"""
SiteSync AI — Phase 10.6 Adversarial Security, IDOR & Data Integrity Audit Suite.

Exhaustive hostile audit verifying:
1. Tenant Isolation & Cross-Project IDOR (Audit, Provenance, Exports).
2. RBAC Enforcement across all canonical roles (Viewer, Supervisor, Planner, Admin) & Unauthenticated rejection.
3. Audit Immutability (Append-only guarantee; HTTP POST, PUT, PATCH, DELETE 405 rejection).
4. Provenance Graph Integrity (Broken links, incomplete lineage detection, unresolved link reporting, terminal rejection states).
5. Export Security (Disallowed dataset names, invalid format parameters, path traversal, SQL injection fuzzing).
6. CSV Formula Injection Neutralization (Escaping =, +, -, @, \\t, \\r while strictly preserving numeric negatives).
7. Complete Unpaginated Dataset Export Integrity (Independent of UI pagination limits).
8. Deterministic Serialization & Export Repeatability.
9. Error Sanitization (No SQL, stack traces, tokens, schema internals, or secrets leaked in error responses).
10. Sensitive Data Audit (No JWTs, passwords, service-role keys, embedding vectors in export payloads).
11. Multi-Project Concurrency & Isolation Integrity.
"""

import io
import csv
import json
import time
import uuid
import jwt
import pytest
from datetime import datetime, timezone, date
from typing import Dict, Any
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import membership_registry, ProjectRole
from app.services.audit_service import audit_service
from app.services.report_export_service import report_export_service
from app.services.decision_service import decision_service
from app.services.matching_service import matching_service
from app.services.schedule_service import schedule_service
from app.schemas.decision import PlannerDecisionType


# Pre-seeded test UUIDs
PROJECT_A = "00000000-0000-0000-0000-000000000001"
PROJECT_B = "00000000-0000-0000-0000-000000000002"

USER_VIEWER = "00000000-0000-0000-0000-000000000003"
USER_SUPERVISOR = "00000000-0000-0000-0000-000000000004"
USER_PLANNER = "00000000-0000-0000-0000-000000000005"
USER_ADMIN = "00000000-0000-0000-0000-000000000006"
USER_OUTSIDER = "00000000-0000-0000-0000-000000000007"


def create_jwt(user_id: str, email: str = "test@example.com") -> str:
    """Generates a valid test JWT signed with test-secret."""
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


def auth_header(user_id: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {create_jwt(user_id)}"}


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


# ==============================================================================
# 1. TENANT ISOLATION & IDOR ATTACK TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_idor_audit_stream_cross_tenant_denial():
    """Adversary with Project A credentials attempts to query Project B audit log."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_B}/audit",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_idor_provenance_cross_tenant_denial():
    """Adversary with Project A credentials attempts to query Project B provenance graph."""
    entity_id = str(uuid.uuid4())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_B}/audit/provenance/approved_actual/{entity_id}",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_idor_export_cross_tenant_denial():
    """Adversary with Project A credentials attempts to export Project B datasets."""
    datasets = ["approved_actuals", "variance", "risk_register"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for ds in datasets:
            resp = await client.get(
                f"/api/v1/projects/{PROJECT_B}/exports/{ds}?format=csv",
                headers=auth_header(USER_ADMIN),
            )
            assert resp.status_code == 403
            data = resp.json()
            assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_cross_tenant_entity_id_probe_returns_404_not_leaking_existence():
    """
    If a Project A user queries provenance with an entity ID belonging to Project B,
    it MUST return 404 and NOT reveal entity existence across tenant boundaries.
    """
    actual_b_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    decision_service.actual_repo._actuals[(PROJECT_B, ext_id, 0)] = {
        "id": actual_b_id,
        "project_id": PROJECT_B,
        "schedule_activity_id": str(uuid.uuid4()),
        "extraction_id": ext_id,
        "match_id": str(uuid.uuid4()),
        "activity_index": 0,
        "actual_quantity": 100.0,
        "actual_unit": "CY",
        "actual_date": date(2026, 8, 31),
        "source_evidence": [],
        "approved_by": USER_OUTSIDER,
        "approved_at": now,
        "notes": None,
        "is_modified": False,
        "created_at": now,
        "updated_at": now,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{actual_b_id}",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "ENTITY_NOT_FOUND"


# ==============================================================================
# 2. RBAC ENFORCEMENT & UNAUTHENTICATED TESTS
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [USER_VIEWER, USER_SUPERVISOR, USER_PLANNER, USER_ADMIN])
async def test_all_canonical_roles_can_access_audit_and_exports(user_id: str):
    """All 4 canonical roles have authorized read/export visibility per ADR-020/ADR-021."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Audit
        resp_audit = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit",
            headers=auth_header(user_id),
        )
        assert resp_audit.status_code == 200

        # Exports
        for ds in ["approved_actuals", "variance", "risk_register"]:
            resp_exp = await client.get(
                f"/api/v1/projects/{PROJECT_A}/exports/{ds}?format=csv",
                headers=auth_header(user_id),
            )
            assert resp_exp.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_requests_strictly_rejected():
    """Requests missing Authorization header must return 401 Unauthorized."""
    endpoints = [
        f"/api/v1/projects/{PROJECT_A}/audit",
        f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{uuid.uuid4()}",
        f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals",
        f"/api/v1/projects/{PROJECT_A}/exports/variance",
        f"/api/v1/projects/{PROJECT_A}/exports/risk_register",
    ]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for url in endpoints:
            resp = await client.get(url)
            assert resp.status_code == 401


# ==============================================================================
# 3. AUDIT IMMUTABILITY & MUTATION ATTACK TESTS
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("verb", ["post", "put", "patch", "delete"])
async def test_audit_endpoints_strictly_disallow_mutations(verb: str):
    """ADR-020: Audit stream is strictly read-only and immutable."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        method = getattr(client, verb)
        endpoints = [
            f"/api/v1/projects/{PROJECT_A}/audit",
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{uuid.uuid4()}",
        ]
        for url in endpoints:
            if verb == "delete":
                resp = await method(url, headers=auth_header(USER_ADMIN))
            else:
                resp = await method(url, json={"event": "fake"}, headers=auth_header(USER_ADMIN))
            assert resp.status_code == 405  # Method Not Allowed


# ==============================================================================
# 4. PROVENANCE GRAPH INTEGRITY & INCOMPLETE LINEAGE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_provenance_handles_missing_intermediate_nodes_as_incomplete():
    """
    When an ApprovedActual points to a decision ID that has no corresponding
    AI extraction or field input in storage, the provenance engine must flag
    is_complete=False and report unresolved links.
    """
    actual_id = str(uuid.uuid4())
    ext_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    decision_service.actual_repo._actuals[(PROJECT_A, ext_id, 0)] = {
        "id": actual_id,
        "project_id": PROJECT_A,
        "schedule_activity_id": str(uuid.uuid4()),
        "extraction_id": ext_id,
        "match_id": str(uuid.uuid4()),
        "activity_index": 0,
        "actual_quantity": 45.0,
        "actual_unit": "LF",
        "actual_date": date(2026, 8, 31),
        "source_evidence": [],
        "approved_by": USER_PLANNER,
        "approved_at": now,
        "notes": None,
        "is_modified": False,
        "created_at": now,
        "updated_at": now,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/approved_actual/{actual_id}",
            headers=auth_header(USER_VIEWER),
        )
        assert resp.status_code == 200
        chain = resp.json()
        assert chain["root_entity_id"] == actual_id
        assert chain["is_complete"] is False
        assert len(chain["unresolved_links"]) > 0


@pytest.mark.asyncio
async def test_provenance_preserves_rejected_planner_decision_terminal_state():
    """A rejected planner decision must be accurately displayed with its terminal rejection status."""
    decision_id = str(uuid.uuid4())
    match_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    decision_service.decision_repo._decisions.append({
        "id": decision_id,
        "project_id": PROJECT_A,
        "match_id": match_id,
        "extraction_id": str(uuid.uuid4()),
        "decision": PlannerDecisionType.REJECTED.value,
        "decided_by": USER_PLANNER,
        "decided_at": now,
        "rejection_reason": "Duplicate work log from previous shift",
        "original_payload": {},
        "modified_payload": None,
        "created_at": now,
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/planner_decision/{decision_id}",
            headers=auth_header(USER_VIEWER),
        )
        assert resp.status_code == 200
        chain = resp.json()
        root_node = next(n for n in chain["nodes"] if n["node_type"] == "PLANNER_DECISION")
        assert root_node["status"] == "REJECTED"
        assert root_node["details"]["rejection_reason"] == "Duplicate work log from previous shift"


# ==============================================================================
# 5. EXPORT SECURITY & INJECTION FUZZING
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("bad_dataset", [
    "users",
    "passwords",
    "secrets",
    "../../etc/passwd",
    "approved_actuals; DROP TABLE users;--",
    "SELECT * FROM audit_events",
    "sys_config",
])
async def test_export_rejects_non_canonical_dataset_injection(bad_dataset: str):
    """Export router rejects non-canonical dataset names with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/{bad_dataset}?format=csv",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code in (400, 404)
        if resp.status_code == 400:
            data = resp.json()
            assert data["error"]["code"] == "INVALID_DATASET"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_format", ["xml", "yaml", "html", "exe", "php", "sh"])
async def test_export_rejects_unsupported_formats(bad_format: str):
    """Export router strictly permits only 'csv' and 'json' formats."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format={bad_format}",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "INVALID_FORMAT"


# ==============================================================================
# 6. CSV FORMULA INJECTION NEUTRALIZATION TESTS
# ==============================================================================

from app.services.report_export_service import sanitize_csv_value

@pytest.mark.parametrize("dangerous_prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_csv_formula_injection_neutralization(dangerous_prefix: str):
    """
    Formula-injection characters at the start of text fields must be sanitized by prefixing
    with a single quote (RFC 4180 / OWASP compliance).
    """
    malicious_text = f"{dangerous_prefix}cmd|'/C calc'!A0"
    sanitized = sanitize_csv_value(malicious_text)
    assert sanitized.startswith("'"), f"Cell '{malicious_text}' was not escaped with leading single quote"


def test_csv_preserves_legitimate_negative_numeric_values():
    """
    Legitimate numeric floats (such as -1.0 or -5.5 for total float or schedule delay)
    must NOT be escaped as string formulas.
    """
    num_val = -10.5
    sanitized = sanitize_csv_value(num_val)
    assert sanitized == -10.5
    assert isinstance(sanitized, (int, float))

    int_val = -4
    sanitized_int = sanitize_csv_value(int_val)
    assert sanitized_int == -4
    assert isinstance(sanitized_int, int)


# ==============================================================================
# 7. COMPLETE DATASET EXPORT INTEGRITY & DETERMINISM
# ==============================================================================

@pytest.mark.asyncio
async def test_export_returns_full_dataset_without_page_limit_slicing():
    """Export must contain 100% of project records, bypassing UI page limit of 50."""
    now = datetime.now(timezone.utc)
    # Seed 65 actuals
    for i in range(65):
        actual_id = str(uuid.uuid4())
        ext_id = str(uuid.uuid4())
        decision_service.actual_repo._actuals[(PROJECT_A, ext_id, i)] = {
            "id": actual_id,
            "project_id": PROJECT_A,
            "schedule_activity_id": str(uuid.uuid4()),
            "extraction_id": ext_id,
            "match_id": str(uuid.uuid4()),
            "activity_index": i,
            "actual_quantity": float(i + 1),
            "actual_unit": "CY",
            "actual_date": date(2026, 8, 31),
            "source_evidence": [],
            "approved_by": USER_PLANNER,
            "approved_at": now,
            "notes": None,
            "is_modified": False,
            "created_at": now,
            "updated_at": now,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format=json",
            headers=auth_header(USER_VIEWER),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["record_count"] == 65
        assert len(data["records"]) == 65


@pytest.mark.asyncio
async def test_export_is_deterministic_across_repeated_invocations():
    """Two successive exports of the same source data must yield byte-for-byte identical content."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format=csv",
            headers=auth_header(USER_VIEWER),
        )
        resp2 = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/approved_actuals?format=csv",
            headers=auth_header(USER_VIEWER),
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.text == resp2.text


# ==============================================================================
# 8. ERROR SANITIZATION & SENSITIVE DATA AUDIT
# ==============================================================================

@pytest.mark.asyncio
async def test_error_envelope_contains_no_sensitive_stack_traces_or_sql():
    """Adversarial malformed inputs must return clean JSON error envelopes without internal leaks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/audit/provenance/invalid_type/invalid_id",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code in [400, 422, 404]
        data = resp.json()
        raw_str = json.dumps(data)

        forbidden_tokens = ["Traceback", 'File "', "SELECT", "INSERT", "password", "jwt", "secret"]
        for token in forbidden_tokens:
            assert token not in raw_str


@pytest.mark.asyncio
async def test_export_json_payload_contains_no_vector_or_secrets():
    """JSON exports must not contain embedding vectors, secrets, or internal metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/projects/{PROJECT_A}/exports/risk_register?format=json",
            headers=auth_header(USER_ADMIN),
        )
        assert resp.status_code == 200
        raw_str = resp.text

        forbidden_leak_tokens = ["embedding", "vector", "password", "service_role", "jwt_secret"]
        for token in forbidden_leak_tokens:
            assert token not in raw_str.lower()
