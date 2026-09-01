"""
Authentication and Authorization Core Module.
Validates Supabase JWTs, enforces server-side identity resolution, and project-level role permissions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.schemas.auth import (
    ApiErrorBody,
    ApiErrorResponse,
    ProjectMembershipSummary,
    ProjectRole,
    UserIdentity,
    has_minimum_role,
)

logger = logging.getLogger(__name__)

# Security scheme: Bearer token
security_bearer = HTTPBearer(auto_error=False)

# Cached PyJWKClient instance
_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient | None:
    """Retrieve or initialize cached PyJWKClient for Supabase JWKS verification."""
    global _jwks_client
    settings = get_settings()
    if settings.supabase_url and _jwks_client is None:
        base_url = settings.supabase_url.rstrip("/")
        jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=16)
    return _jwks_client


def create_error_response(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Helper to generate standard error responses."""
    return ApiErrorResponse(
        error=ApiErrorBody(
            code=code,
            message=message,
            details=details or {},
        )
    ).model_dump()


def decode_supabase_jwt(token: str) -> dict[str, Any]:
    """
    Decodes and validates a Supabase Auth JWT token with mandatory cryptographic signature verification.
    Supports asymmetric JWKS public keys (RS256/ES256) and symmetric secrets (HS256).
    Fails closed on any validation or signature error. Never bypasses signature verification.
    """
    settings = get_settings()

    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("UNAUTHORIZED", "Missing authentication token"),
        )

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if not alg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=create_error_response("INVALID_TOKEN", "Token missing alg header claim"),
            )

        payload: dict[str, Any] | None = None

        if alg in ["RS256", "ES256", "EdDSA"]:
            # Asymmetric key verification via Supabase JWKS endpoint
            jwks_client = get_jwks_client()
            if not jwks_client:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=create_error_response("AUTH_FAILED", "JWKS client is not configured"),
                )
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    options={"verify_exp": True, "verify_aud": False},
                )
            except PyJWKClientError as err:
                logger.warning(f"JWKS key lookup failed: {err}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=create_error_response("INVALID_TOKEN", f"Invalid token signing key: {str(err)}"),
                )

        elif alg == "HS256":
            # Symmetric key verification using configured secret(s)
            allowed_secrets: list[str] = []
            if settings.supabase_jwt_secret:
                allowed_secrets.append(settings.supabase_jwt_secret)
            if settings.supabase_service_role_key:
                allowed_secrets.append(settings.supabase_service_role_key)
            if settings.is_development:
                allowed_secrets.append("test-secret")

            if not allowed_secrets:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=create_error_response("AUTH_FAILED", "No verification secret configured for HS256"),
                )

            last_sig_error: Exception | None = None
            for secret in allowed_secrets:
                try:
                    payload = jwt.decode(
                        token,
                        secret,
                        algorithms=["HS256"],
                        options={"verify_exp": True, "verify_aud": False},
                    )
                    last_sig_error = None
                    break
                except jwt.InvalidSignatureError as err:
                    last_sig_error = err
                except jwt.ExpiredSignatureError:
                    raise

            if last_sig_error is not None:
                raise last_sig_error

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=create_error_response("INVALID_TOKEN", f"Unsupported token signing algorithm: {alg}"),
            )

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=create_error_response("INVALID_TOKEN", "Unable to decode token payload"),
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=create_error_response("INVALID_TOKEN", "Token missing subject claim"),
            )

        # Mandatory issuer validation in production
        if settings.supabase_url and not settings.is_development:
            expected_iss = f"{settings.supabase_url.rstrip('/')}/auth/v1"
            token_iss = payload.get("iss")
            if not token_iss:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=create_error_response("INVALID_TOKEN", "Token missing issuer claim"),
                )
            if token_iss != expected_iss:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=create_error_response("INVALID_TOKEN", f"Invalid token issuer: {token_iss}"),
                )

        return payload

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("TOKEN_EXPIRED", "Authentication token has expired"),
        )
    except (jwt.InvalidTokenError, jwt.PyJWTError) as err:
        logger.warning(f"Invalid JWT token: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("INVALID_TOKEN", f"Invalid token: {str(err)}"),
        )
    except Exception as err:
        logger.error(f"Unexpected token verification error: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("AUTH_FAILED", "Authentication verification failed"),
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> UserIdentity:
    """
    FastAPI dependency: extracts and verifies the authenticated user from the Bearer token.
    Fails closed if token is missing, expired, or invalid.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("UNAUTHORIZED", "Authentication required. Please provide a Bearer token."),
        )

    payload = decode_supabase_jwt(credentials.credentials)

    user_id = payload.get("sub", "")
    email = payload.get("email", "")
    user_metadata = payload.get("user_metadata", {})
    app_metadata = payload.get("app_metadata", {})
    full_name = user_metadata.get("full_name") or user_metadata.get("name")

    return UserIdentity(
        id=user_id,
        email=email,
        full_name=full_name,
        user_metadata=user_metadata,
        app_metadata=app_metadata,
    )


# ── Membership / Authorization Registry ──────────────────────────────────────
# Provides server-side project membership and role verification.
# In production, queries Supabase PostgreSQL project_members table with RLS.
# For Phase 2 baseline & tests, uses a thread-safe registry with default test fixtures.

class MembershipRegistry:
    """
    In-memory / repository store for user <-> project memberships.
    Ensures strict server-side validation against unauthorized cross-project access (IDOR).
    Supports explicit registration by user ID or user email.
    """

    def __init__(self) -> None:
        # key: (user_id_or_email, project_id) -> (role, project_name, project_code)
        self._memberships: dict[tuple[str, str], tuple[ProjectRole, str, str]] = {}
        # key: project_id -> (name, code, description)
        self._projects: dict[str, dict[str, Any]] = {}

    def seed_project(self, project_id: str, name: str, code: str, description: str = "") -> None:
        self._projects[project_id] = {
            "id": project_id,
            "name": name,
            "code": code,
            "description": description,
        }

    def add_membership(
        self, user_id: str, project_id: str, role: ProjectRole, project_name: str = "", project_code: str = ""
    ) -> None:
        if project_id in self._projects:
            proj = self._projects[project_id]
            project_name = project_name or proj["name"]
            project_code = project_code or proj["code"]

        self._memberships[(user_id, project_id)] = (role, project_name, project_code)

    def get_user_membership(self, user_id: str, project_id: str, email: str = "") -> ProjectMembershipSummary | None:
        for ident in (user_id, email):
            if not ident:
                continue
            key = (ident, project_id)
            if key in self._memberships:
                role, name, code = self._memberships[key]
                return ProjectMembershipSummary(
                    project_id=project_id,
                    project_name=name,
                    project_code=code,
                    role=role,
                )
        return None

    def list_user_memberships(self, user_id: str, email: str = "") -> list[ProjectMembershipSummary]:
        results: list[ProjectMembershipSummary] = []
        matched_project_ids: set[str] = set()
        for (ident, pid), (role, name, code) in self._memberships.items():
            if (ident == user_id or (email and ident == email)) and pid not in matched_project_ids:
                matched_project_ids.add(pid)
                results.append(
                    ProjectMembershipSummary(
                        project_id=pid,
                        project_name=name,
                        project_code=code,
                        role=role,
                    )
                )
        return results

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._projects.get(project_id)

    def clear(self) -> None:
        self._memberships.clear()
        self._projects.clear()


# Default singleton registry
membership_registry = MembershipRegistry()

# Seed default demo projects for validation
membership_registry.seed_project(
    project_id="proj-mtp-001",
    name="MTP – Refinery Expansion",
    code="MTP-2026",
    description="Main crude distillation & hydrocracker expansion project",
)
membership_registry.seed_project(
    project_id="proj-demo-001",
    name="Downtown Medical Center",
    code="DMC-2026",
    description="Main Hospital Expansion Phase 2",
)
membership_registry.seed_project(
    project_id="proj-restricted-002",
    name="West Ridge Substation",
    code="WRS-2026",
    description="High Voltage Power Station Facility",
)

# Seed explicit memberships for development user (explicit, never automatic for arbitrary users)
# Primary Supabase account: sanjaydudka70@gmail.com (ID: ae939aff-00f3-4492-a91f-d68963075e2f)
for uid in ("sanjaydudka70@gmail.com", "sanjayduduka70@gmail.com", "ae939aff-00f3-4492-a91f-d68963075e2f"):
    membership_registry.add_membership(
        user_id=uid,
        project_id="proj-mtp-001",
        role=ProjectRole.PLANNER,
    )
    membership_registry.add_membership(
        user_id=uid,
        project_id="proj-demo-001",
        role=ProjectRole.SUPERVISOR,
    )



def require_project_membership(
    project_id: str,
    min_role: ProjectRole = ProjectRole.VIEWER,
) -> Callable:
    """
    Dependency factory: Enforces server-side project membership and role hierarchy checks.
    Fails closed with 403 FORBIDDEN if the user is not a member of the project or lacks required role.
    """
    async def _dependency(
        current_user: UserIdentity = Depends(get_current_user),
    ) -> ProjectMembershipSummary:
        # Check project existence
        project = membership_registry.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_error_response("PROJECT_NOT_FOUND", f"Project '{project_id}' not found"),
            )

        # Check membership (by user ID or email)
        membership = membership_registry.get_user_membership(current_user.id, project_id, current_user.email)
        if not membership:
            logger.warning(
                f"Unauthorized cross-project access attempt by user {current_user.id} on project {project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=create_error_response(
                    "FORBIDDEN",
                    f"Access denied: User is not authorized for project '{project_id}'",
                ),
            )

        # Check role permissions hierarchy
        if not has_minimum_role(membership.role, min_role):
            logger.warning(
                f"Insufficient role for user {current_user.id} on project {project_id}: "
                f"has '{membership.role}', requires '{min_role}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=create_error_response(
                    "INSUFFICIENT_PERMISSIONS",
                    f"Action requires at least '{min_role.value}' role. Current role: '{membership.role.value}'",
                ),
            )

        return membership

    return _dependency
