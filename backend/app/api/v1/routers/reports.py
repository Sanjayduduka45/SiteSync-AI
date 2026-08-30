"""
Reports API Router — SiteSync AI Phase 3.
Provides secure endpoints for project-scoped field reports.
Endpoints:
  - GET    /api/v1/projects/{project_id}/reports
  - GET    /api/v1/projects/{project_id}/reports/{report_id}
  - POST   /api/v1/projects/{project_id}/reports
  - DELETE /api/v1/projects/{project_id}/reports/{report_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.reports import (
    ReportCreate,
    ReportListResponse,
    ReportResponse,
)
from app.services.report_service import report_service

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


def _verify_membership(
    project_id: str,
    current_user: UserIdentity,
    min_role: ProjectRole = ProjectRole.VIEWER,
):
    """Enforce server-side project existence, membership, and role check."""
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

    if not has_minimum_role(membership.role, min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                "INSUFFICIENT_PERMISSIONS",
                f"Action requires at least '{min_role.value}' role. Current role: '{membership.role.value}'",
            ),
        )

    return membership


@router.get("", response_model=ReportListResponse, summary="List project reports")
async def list_reports(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ReportListResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    return report_service.list_reports(project_id)


@router.get("/{report_id}", response_model=ReportResponse, summary="Get project report by ID")
async def get_report(
    project_id: str,
    report_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ReportResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    report = report_service.get_report(project_id, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("REPORT_NOT_FOUND", f"Report '{report_id}' not found in project '{project_id}'"),
        )
    return report


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create/Upload a project report record",
)
async def create_report(
    project_id: str,
    payload: ReportCreate,
    current_user: UserIdentity = Depends(get_current_user),
) -> ReportResponse:
    # Requires SUPERVISOR role or above
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)
    return report_service.create_report(
        project_id=project_id,
        data=payload,
        uploaded_by_id=current_user.id,
        uploaded_by_email=current_user.email,
    )


@router.delete(
    "/{report_id}",
    summary="Delete a project report",
)
async def delete_report(
    project_id: str,
    report_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> dict[str, str]:
    # Requires ADMIN role
    _verify_membership(project_id, current_user, min_role=ProjectRole.ADMIN)
    deleted = report_service.delete_report(project_id, report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("REPORT_NOT_FOUND", f"Report '{report_id}' not found in project '{project_id}'"),
        )
    return {"status": "deleted", "id": report_id}
