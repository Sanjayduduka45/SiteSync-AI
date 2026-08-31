"""
SiteSync AI — Phase 7.4 Planner Decision & Approved Actuals API Router.
Provides secure multi-tenant HTTP endpoints for:
  - Human planner approval of AI match recommendations
  - Human planner rejection with mandatory justification
  - Human planner modification with schedule activity overrides
  - Querying planner decision audit records
  - Querying official approved construction progress actuals with pagination and filters

Tenant isolation and RBAC:
  - project_id is strictly derived from the URL path.
  - planner_id / decided_by / approved_by is strictly bound to the authenticated UserIdentity.
  - Mutations (approve, reject, modify) require PLANNER or ADMIN role.
  - Reads (decision, approved-actuals) require VIEWER, SUPERVISOR, PLANNER, or ADMIN role.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.decision import (
    ApproveMatchRequest,
    ApprovedActualListResponse,
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    RejectMatchRequest,
)
from app.services.decision_service import (
    ApprovedActualPersistenceError,
    CrossProjectDecisionError,
    DecisionPersistenceError,
    ExtractionNotFoundError,
    InvalidDecisionError,
    MatchNotFoundError,
    ScheduleActivityNotFoundError,
    decision_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["decisions"])


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
# Approve Match Endpoint
# ==============================================================================

@router.post(
    "/matches/{match_id}/approve",
    response_model=ApprovedActualResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve an AI match recommendation as-is",
)
async def approve_match(
    project_id: str,
    match_id: str,
    request: ApproveMatchRequest = ApproveMatchRequest(),
    current_user: UserIdentity = Depends(get_current_user),
) -> ApprovedActualResponse:
    """
    Approves an AI match recommendation as-is, records the planner decision audit log,
    and idempotently creates an official approved actual record.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)

    try:
        approved_actual = await decision_service.approve_match(
            project_id=project_id,
            match_id=match_id,
            planner_id=current_user.id,
            notes=request.notes,
        )
        return approved_actual
    except MatchNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("MATCH_NOT_FOUND", str(err)),
        )
    except ExtractionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EXTRACTION_NOT_FOUND", str(err)),
        )
    except ScheduleActivityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("SCHEDULE_ACTIVITY_NOT_FOUND", str(err)),
        )
    except CrossProjectDecisionError as err:
        logger.warning(f"Tenant boundary violation in approve_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response("TENANT_VIOLATION", "Cross-project decision action rejected"),
        )
    except InvalidDecisionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DECISION", str(err)),
        )
    except (DecisionPersistenceError, ApprovedActualPersistenceError) as err:
        logger.error(f"Persistence error in approve_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to persist decision or approved actual"),
        )
    except Exception as err:
        logger.error(f"Unexpected error approving match '{match_id}' in project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "An unexpected error occurred"),
        )


# ==============================================================================
# Reject Match Endpoint
# ==============================================================================

@router.post(
    "/matches/{match_id}/reject",
    response_model=PlannerDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject an AI match recommendation with mandatory justification",
)
async def reject_match(
    project_id: str,
    match_id: str,
    request: RejectMatchRequest,
    current_user: UserIdentity = Depends(get_current_user),
) -> PlannerDecisionResponse:
    """
    Rejects an AI match recommendation, recording the planner decision audit log
    with a mandatory human explanation. Does NOT create an approved actual record.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)

    try:
        decision = await decision_service.reject_match(
            project_id=project_id,
            match_id=match_id,
            planner_id=current_user.id,
            rejection_reason=request.rejection_reason,
        )
        return decision
    except MatchNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("MATCH_NOT_FOUND", str(err)),
        )
    except ExtractionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EXTRACTION_NOT_FOUND", str(err)),
        )
    except ScheduleActivityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("SCHEDULE_ACTIVITY_NOT_FOUND", str(err)),
        )
    except CrossProjectDecisionError as err:
        logger.warning(f"Tenant boundary violation in reject_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response("TENANT_VIOLATION", "Cross-project decision action rejected"),
        )
    except InvalidDecisionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DECISION", str(err)),
        )
    except DecisionPersistenceError as err:
        logger.error(f"Persistence error in reject_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to persist planner decision"),
        )
    except Exception as err:
        logger.error(f"Unexpected error rejecting match '{match_id}' in project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "An unexpected error occurred"),
        )


# ==============================================================================
# Modify Match Endpoint
# ==============================================================================

@router.post(
    "/matches/{match_id}/modify",
    response_model=ApprovedActualResponse,
    status_code=status.HTTP_200_OK,
    summary="Modify AI match recommendation and approve",
)
async def modify_match(
    project_id: str,
    match_id: str,
    request: ModifyMatchRequest,
    current_user: UserIdentity = Depends(get_current_user),
) -> ApprovedActualResponse:
    """
    Modifies an AI match recommendation before approval (e.g. reassigning schedule activity,
    overriding quantity/date/unit), records the planner decision audit log, and creates the approved actual.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)

    try:
        approved_actual = await decision_service.modify_match(
            project_id=project_id,
            match_id=match_id,
            planner_id=current_user.id,
            modification=request,
        )
        return approved_actual
    except MatchNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("MATCH_NOT_FOUND", str(err)),
        )
    except ExtractionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EXTRACTION_NOT_FOUND", str(err)),
        )
    except ScheduleActivityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("SCHEDULE_ACTIVITY_NOT_FOUND", str(err)),
        )
    except CrossProjectDecisionError as err:
        logger.warning(f"Tenant boundary violation in modify_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response("TENANT_VIOLATION", "Cross-project decision action rejected"),
        )
    except InvalidDecisionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DECISION", str(err)),
        )
    except (DecisionPersistenceError, ApprovedActualPersistenceError) as err:
        logger.error(f"Persistence error in modify_match for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to persist decision or approved actual"),
        )
    except Exception as err:
        logger.error(f"Unexpected error modifying match '{match_id}' in project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "An unexpected error occurred"),
        )


# ==============================================================================
# Get Decision Endpoint
# ==============================================================================

@router.get(
    "/matches/{match_id}/decision",
    response_model=Optional[PlannerDecisionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get latest planner decision audit record for a match recommendation",
)
async def get_match_decision(
    project_id: str,
    match_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> Optional[PlannerDecisionResponse]:
    """
    Retrieves the most recent human planner decision audit record for a match recommendation.
    Strictly scoped to project_id. Returns 200 with decision or 200 with null if no decision exists.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    try:
        decision = await decision_service.get_decision_for_match(
            project_id=project_id,
            match_id=match_id,
        )
        return decision
    except Exception as err:
        logger.error(f"Error retrieving decision for match '{match_id}' in project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve planner decision"),
        )


# ==============================================================================
# List Approved Actuals Endpoint
# ==============================================================================

@router.get(
    "/approved-actuals",
    response_model=ApprovedActualListResponse,
    status_code=status.HTTP_200_OK,
    summary="List approved actual progress records for a project",
)
async def list_approved_actuals(
    project_id: str,
    limit: int = Query(50, ge=1, le=100, description="Max items to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    schedule_activity_id: Optional[UUID] = Query(None, description="Optional filter by schedule activity UUID"),
    from_date: Optional[date] = Query(None, description="Optional start date filter (inclusive)"),
    to_date: Optional[date] = Query(None, description="Optional end date filter (inclusive)"),
    current_user: UserIdentity = Depends(get_current_user),
) -> ApprovedActualListResponse:
    """
    Lists official approved construction progress actuals scoped to the project with pagination and filtering.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "INVALID_DATE_RANGE",
                "from_date must be less than or equal to to_date",
            ),
        )

    try:
        response = await decision_service.list_approved_actuals(
            project_id=project_id,
            limit=limit,
            offset=offset,
            schedule_activity_id=schedule_activity_id,
            from_date=from_date,
            to_date=to_date,
        )
        return response
    except Exception as err:
        logger.error(f"Error listing approved actuals for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve approved actuals"),
        )
