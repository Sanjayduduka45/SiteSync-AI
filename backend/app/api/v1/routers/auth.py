"""
SiteSync AI — Phase 2 Authentication & Authorization Router.
Endpoints:
  - GET  /api/v1/auth/me: Returns current authenticated user and project memberships
  - GET  /api/v1/projects/{project_id}: Returns project details with server-side authorization
  - POST /api/v1/projects/{project_id}/admin-check: Verifies admin role enforcement
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
    require_project_membership,
)
from app.schemas.auth import (
    AuthMeResponse,
    ProjectDetailResponse,
    ProjectMembershipSummary,
    ProjectRole,
    UserIdentity,
    has_minimum_role,
)

router = APIRouter(tags=["auth"])


@router.get(
    "/auth/me",
    response_model=AuthMeResponse,
    summary="Get current authenticated user identity and project memberships",
)
async def get_me(
    current_user: UserIdentity = Depends(get_current_user),
) -> AuthMeResponse:
    """
    Returns the authenticated user's profile identity and list of authorized project memberships.
    Server derives identity solely from the validated JWT token.
    """
    memberships = membership_registry.list_user_memberships(current_user.id)
    return AuthMeResponse(
        user=current_user,
        memberships=memberships,
    )


@router.get(
    "/projects/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details with server-side membership check",
)
async def get_project_details(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ProjectDetailResponse:
    """
    Returns project details if and only if the requesting authenticated user is an authorized member.
    Enforces server-side authorization and prevents IDOR / cross-tenant leakage.
    """
    project = membership_registry.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("PROJECT_NOT_FOUND", f"Project '{project_id}' not found"),
        )

    membership = membership_registry.get_user_membership(current_user.id, project_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                "FORBIDDEN",
                f"Access denied: User is not authorized for project '{project_id}'",
            ),
        )

    return ProjectDetailResponse(
        id=project["id"],
        name=project["name"],
        code=project["code"],
        description=project.get("description"),
        user_role=membership.role,
    )


@router.post(
    "/projects/{project_id}/admin-check",
    summary="Verify role-gated admin authorization",
)
async def admin_role_check(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> dict[str, str]:
    """
    Verifies that only users with 'admin' role in this project can perform privileged actions.
    """
    project = membership_registry.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("PROJECT_NOT_FOUND", f"Project '{project_id}' not found"),
        )

    membership = membership_registry.get_user_membership(current_user.id, project_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                "FORBIDDEN",
                f"Access denied: User is not authorized for project '{project_id}'",
            ),
        )

    if not has_minimum_role(membership.role, ProjectRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                "INSUFFICIENT_PERMISSIONS",
                f"Action requires 'admin' role. Current role: '{membership.role.value}'",
            ),
        )

    return {"status": "ok", "message": f"User {current_user.id} has admin authorization on {project_id}"}
