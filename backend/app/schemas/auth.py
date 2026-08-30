"""
Auth & Authorization Pydantic Schemas.
Defines user identity, project roles, membership, and standard error responses.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ProjectRole(str, Enum):
    """
    Project-level authorization roles.
    Hierarchical ordering: ADMIN > PLANNER > SUPERVISOR > VIEWER
    """
    ADMIN = "admin"
    PLANNER = "planner"
    SUPERVISOR = "supervisor"
    VIEWER = "viewer"


_ROLE_WEIGHTS: dict[ProjectRole, int] = {
    ProjectRole.ADMIN: 40,
    ProjectRole.PLANNER: 30,
    ProjectRole.SUPERVISOR: 20,
    ProjectRole.VIEWER: 10,
}


def has_minimum_role(current_role: ProjectRole, required_role: ProjectRole) -> bool:
    """Check if current_role satisfies required_role in the role hierarchy."""
    return _ROLE_WEIGHTS.get(current_role, 0) >= _ROLE_WEIGHTS.get(required_role, 0)


class UserIdentity(BaseModel):
    """Authenticated user profile identity."""
    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    full_name: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectMembershipSummary(BaseModel):
    """Summary of a user's membership and role in a project."""
    model_config = ConfigDict(frozen=True)

    project_id: str
    project_name: str
    project_code: str
    role: ProjectRole


class AuthMeResponse(BaseModel):
    """Response returned by GET /api/v1/auth/me."""
    model_config = ConfigDict(frozen=True)

    user: UserIdentity
    memberships: list[ProjectMembershipSummary] = Field(default_factory=list)


class ProjectDetailResponse(BaseModel):
    """Response returned for authorized project queries."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    code: str
    description: str | None = None
    user_role: ProjectRole


class ApiErrorBody(BaseModel):
    """Standard error body schema per ARCHITECTURE.md."""
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Standard error wrapper schema."""
    model_config = ConfigDict(frozen=True)

    error: ApiErrorBody
