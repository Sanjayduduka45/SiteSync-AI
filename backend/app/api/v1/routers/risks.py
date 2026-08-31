"""
SiteSync AI — Phase 9.5 Risk Intelligence & Downstream Impact API Router.
Provides secure multi-tenant HTTP endpoints for:
  - Project-level risk intelligence summary and severity taxonomy distribution (Viewer+)
  - Paginated activity risk register with server-side filtering (Viewer+)
  - Transitive downstream impact and float erosion analysis for an activity (Viewer+)

Tenant containment and RBAC:
  - project_id is strictly derived from the URL path.
  - All endpoints permit VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
  - All domain calculations delegate to Phase 8, 9.2, 9.3, and 9.4 services.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.downstream_impact import DownstreamImpactResult
from app.schemas.risk import (
    ActivityRiskListResponse,
    ProjectRiskSummary,
    RiskCategory,
    RiskSeverityLevel,
)
from app.services.cpm_service import CPMGraphCycleError, CPMValidationError
from app.services.risk_query_service import (
    RiskActivityNotFoundError,
    risk_query_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/risks", tags=["risks"])

ALLOWED_SEVERITY_LEVELS = {s.value for s in RiskSeverityLevel}
ALLOWED_RISK_CATEGORIES = {c.value for c in RiskCategory}


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
# Risk Summary Endpoint
# ==============================================================================

@router.get(
    "/summary",
    response_model=ProjectRiskSummary,
    status_code=status.HTTP_200_OK,
    summary="Get project-wide schedule risk intelligence summary and severity taxonomy counts",
)
async def get_project_risk_summary(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ProjectRiskSummary:
    """
    Returns aggregated project risk metrics, severity distribution, category counts,
    and average risk scores computed deterministically.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        summary = await risk_query_service.get_project_risk_summary(project_id=project_id)
        return summary
    except CPMGraphCycleError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("CYCLE_DETECTED", "Dependency cycle detected."),
        )
    except CPMValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_SCHEDULE_NETWORK", str(err)),
        )
    except Exception as err:
        logger.error(f"Failed to get project risk summary for '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve project risk summary"),
        )


# ==============================================================================
# Risk Activities List Endpoint
# ==============================================================================

@router.get(
    "/activities",
    response_model=ActivityRiskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated schedule activities with risk assessments and filtering",
)
async def list_risk_activities(
    project_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page size (1 to 100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    severity: Optional[str] = Query(None, description="Filter by discrete risk severity level"),
    category: Optional[str] = Query(None, description="Filter by canonical risk category"),
    wbs_code: Optional[str] = Query(None, description="Filter by WBS code"),
    discipline: Optional[str] = Query(None, description="Filter by trade discipline"),
    current_user: UserIdentity = Depends(get_current_user),
) -> ActivityRiskListResponse:
    """
    Returns itemized activity risk assessments with server-side filtering and pagination.
    Sorted deterministically by severity rank (CRITICAL < HIGH < MEDIUM < LOW),
    risk_score DESC, activity_code ASC, activity_id ASC.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    sev_enum: Optional[RiskSeverityLevel] = None
    if severity is not None:
        if severity not in ALLOWED_SEVERITY_LEVELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    "INVALID_SEVERITY_FILTER",
                    f"severity must be one of: {', '.join(sorted(ALLOWED_SEVERITY_LEVELS))}",
                ),
            )
        sev_enum = RiskSeverityLevel(severity)

    cat_enum: Optional[RiskCategory] = None
    if category is not None:
        if category not in ALLOWED_RISK_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    "INVALID_CATEGORY_FILTER",
                    f"category must be one of: {', '.join(sorted(ALLOWED_RISK_CATEGORIES))}",
                ),
            )
        cat_enum = RiskCategory(category)

    try:
        items, total = await risk_query_service.list_risk_activities(
            project_id=project_id,
            severity=sev_enum,
            category=cat_enum,
            wbs_code=wbs_code,
            discipline=discipline,
            limit=limit,
            offset=offset,
        )
        return ActivityRiskListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except CPMGraphCycleError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("CYCLE_DETECTED", "Dependency cycle detected."),
        )
    except CPMValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_SCHEDULE_NETWORK", str(err)),
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Failed to list risk activities for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve risk activities"),
        )


# ==============================================================================
# Downstream Impact Endpoint
# ==============================================================================

@router.get(
    "/downstream-impact/{activity_id}",
    response_model=DownstreamImpactResult,
    status_code=status.HTTP_200_OK,
    summary="Get transitive downstream impact and float erosion for a schedule activity",
)
async def get_downstream_impact(
    project_id: str,
    activity_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> DownstreamImpactResult:
    """
    Evaluates the full transitive DAG of downstream successors reachable from the source activity.
    Classifies impact into critical slippage vs buffer absorbed based on float erosion.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        impact = await risk_query_service.get_downstream_impact(
            project_id=project_id,
            activity_id=activity_id,
        )
        return impact
    except RiskActivityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("ACTIVITY_NOT_FOUND", str(err)),
        )
    except CPMGraphCycleError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("CYCLE_DETECTED", "Dependency cycle detected."),
        )
    except CPMValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_SCHEDULE_NETWORK", str(err)),
        )
    except Exception as err:
        logger.error(
            f"Failed to get downstream impact for activity '{activity_id}' in project '{project_id}': {err}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to evaluate downstream impact"),
        )
