"""
SiteSync AI — Phase 8.2 Plan vs Actual Variance API Router.
Provides secure multi-tenant HTTP endpoints for:
  - High-level project plan vs actual variance summary and KPIs
  - Paginated activity-level plan vs actual variance items with filtering
  - WBS-tier variance rollups grouped by homogeneous physical units

Tenant containment and RBAC:
  - project_id is strictly derived from the URL path.
  - All read endpoints permit VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
  - Mutations are strictly prohibited (Phase 8.2 is 100% read-only).
  - All mathematical operations delegate to the Phase 8.1 pure variance engine.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.variance import (
    ActivityVarianceListResponse,
    ActivityVarianceStatus,
    ProjectVarianceSummary,
    WbsVarianceListResponse,
)
from app.services.variance_query_service import variance_query_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/variance", tags=["variance"])

ALLOWED_VARIANCE_STATUSES = {s.value for s in ActivityVarianceStatus}


def _verify_membership(
    project_id: str,
    current_user: UserIdentity,
    min_role: ProjectRole = ProjectRole.VIEWER,
):
    """Enforces server-side project existence, user membership, and role authorization."""
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


# ==============================================================================
# Project Variance Summary Endpoint
# ==============================================================================

@router.get(
    "/summary",
    response_model=ProjectVarianceSummary,
    status_code=status.HTTP_200_OK,
    summary="Get project-wide Plan vs Actual variance summary and homogeneous unit rollups",
)
async def get_project_variance_summary(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
):
    """
    Returns high-level project variance KPIs and homogeneous physical unit rollups.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        summary = await variance_query_service.get_project_summary(project_id=project_id)
        return summary
    except Exception as err:
        logger.error(f"Failed to get project variance summary: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve project variance summary"),
        )


# ==============================================================================
# Activity Variance List Endpoint
# ==============================================================================

@router.get(
    "/activities",
    response_model=ActivityVarianceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated activity-level Plan vs Actual variance items",
)
async def list_activity_variances(
    project_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page size (1 to 100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    wbs_code: Optional[str] = Query(None, description="Filter by WBS code"),
    discipline: Optional[str] = Query(None, description="Filter by trade discipline"),
    variance_status: Optional[str] = Query(None, description="Filter by calculated variance status"),
    from_date: Optional[date] = Query(None, description="Filter actuals recorded on or after this date"),
    to_date: Optional[date] = Query(None, description="Filter actuals recorded on or before this date"),
    current_user: UserIdentity = Depends(get_current_user),
):
    """
    Returns itemized Plan vs Actual variance records for schedule activities.
    Supports filtering by WBS, discipline, variance status, and actual date range.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DATE_RANGE", "from_date must be less than or equal to to_date"),
        )

    if variance_status is not None and variance_status not in ALLOWED_VARIANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "INVALID_VARIANCE_STATUS",
                f"variance_status must be one of: {', '.join(sorted(ALLOWED_VARIANCE_STATUSES))}",
            ),
        )

    try:
        items, total = await variance_query_service.list_activity_variances(
            project_id=project_id,
            limit=limit,
            offset=offset,
            wbs_code=wbs_code,
            discipline=discipline,
            variance_status=variance_status,
            from_date=from_date,
            to_date=to_date,
        )
        return ActivityVarianceListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Failed to list activity variances: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve activity variances"),
        )


# ==============================================================================
# WBS Rollup List Endpoint
# ==============================================================================

@router.get(
    "/wbs",
    response_model=WbsVarianceListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get WBS-tier variance rollups grouped by homogeneous physical units",
)
async def get_wbs_variance_rollups(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
):
    """
    Returns WBS tier rollups aggregated strictly across homogeneous units.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        wbs_items = await variance_query_service.get_wbs_rollups(project_id=project_id)
        return WbsVarianceListResponse(
            items=wbs_items,
            total=len(wbs_items),
        )
    except Exception as err:
        logger.error(f"Failed to get WBS variance rollups: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve WBS variance rollups"),
        )
