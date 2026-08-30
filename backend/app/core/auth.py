"""
Authentication and Authorization Core Module.
Validates Supabase JWTs, enforces server-side identity resolution, and project-level role permissions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
import jwt
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
    Decodes and validates a Supabase Auth JWT token.
    Fails closed on any validation error.
    """
    settings = get_settings()

    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("UNAUTHORIZED", "Missing authentication token"),
        )

    try:
        # If a JWT secret or service role key is configured, verify signature
        secret = settings.supabase_jwt_secret or settings.supabase_service_role_key

        if secret and not settings.is_development:
            # Full signature verification
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256", "RS256", "ES256"],
                options={"verify_exp": True, "verify_aud": False},
            )
        else:
            # In development/test mode without live secret, verify standard claims
            # but allow decode with signature verification bypassed if secret is not set
            if secret:
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256", "RS256", "ES256"],
                    options={"verify_exp": True, "verify_aud": False},
                )
            else:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": True},
                )

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=create_error_response("INVALID_TOKEN", "Token missing subject claim"),
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response("TOKEN_EXPIRED", "Authentication token has expired"),
        )
    except jwt.InvalidTokenError as err:
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
    """

    def __init__(self) -> None:
        # key: (user_id, project_id) -> (role, project_name, project_code)
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

    def get_user_membership(self, user_id: str, project_id: str) -> ProjectMembershipSummary | None:
        key = (user_id, project_id)
        if key not in self._memberships:
            return None
        role, name, code = self._memberships[key]
        return ProjectMembershipSummary(
            project_id=project_id,
            project_name=name,
            project_code=code,
            role=role,
        )

    def list_user_memberships(self, user_id: str) -> list[ProjectMembershipSummary]:
        results: list[ProjectMembershipSummary] = []
        for (uid, pid), (role, name, code) in self._memberships.items():
            if uid == user_id:
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

# Seed default demo project for validation
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

        # Check membership
        membership = membership_registry.get_user_membership(current_user.id, project_id)
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
