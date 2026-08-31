"""
Schedule & Matching API Router — SiteSync AI Phase 6.3 & 6.6.
Provides secure multi-tenant endpoints for schedule activity ingestion, retrieval,
and AI-assisted schedule match recommendation generation and persistence.

Endpoints:
  - POST /api/v1/projects/{project_id}/schedules/activities
  - GET  /api/v1/projects/{project_id}/schedules/activities
  - POST /api/v1/projects/{project_id}/extractions/{extraction_id}/match
  - GET  /api/v1/projects/{project_id}/extractions/{extraction_id}/matches
"""

from __future__ import annotations

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.extractions import ExtractedActivity, ExtractionStatus
from app.schemas.schedule import (
    MatchRecommendationListResponse,
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScheduleActivityListResponse,
    ScheduleActivityResponse,
)
from app.services.extraction_service import extraction_service
from app.services.matching_service import (
    CrossProjectCandidateError,
    NoCandidatesError,
    matching_service,
)
from app.services.schedule_service import schedule_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["schedules-matching"])


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
# Schedule Activities Endpoints (Phase 6.3)
# ==============================================================================

@router.post(
    "/schedules/activities",
    response_model=ScheduleActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or idempotently upsert a schedule activity",
)
async def create_schedule_activity(
    project_id: str,
    data: ScheduleActivityCreate,
    current_user: UserIdentity = Depends(get_current_user),
) -> ScheduleActivityResponse:
    """
    Creates or idempotently upserts a baseline schedule activity.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)

    try:
        activity = await schedule_service.create_or_update_activity(
            project_id=project_id,
            data=data,
        )
        return activity
    except Exception as err:
        logger.error(f"Error creating schedule activity for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to save schedule activity"),
        )


@router.get(
    "/schedules/activities",
    response_model=ScheduleActivityListResponse,
    status_code=status.HTTP_200_OK,
    summary="List schedule activities for a project",
)
async def list_schedule_activities(
    project_id: str,
    limit: int = Query(50, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: UserIdentity = Depends(get_current_user),
) -> ScheduleActivityListResponse:
    """
    Lists baseline schedule activities scoped to the project with pagination.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    try:
        response = await schedule_service.list_activities(
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return response
    except Exception as err:
        logger.error(f"Error listing schedule activities for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve schedule activities"),
        )


# ==============================================================================
# Schedule Matching Endpoints (Phase 6.6)
# ==============================================================================

@router.post(
    "/extractions/{extraction_id}/match",
    response_model=MatchRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI schedule matching for an extraction",
)
async def trigger_schedule_matching(
    project_id: str,
    extraction_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> MatchRecommendationListResponse:
    """
    Triggers multi-factor schedule matching for all activities in a completed extraction.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)

    # 1. Fetch extraction and strictly enforce project tenant ownership
    extraction = await extraction_service.get_extraction(project_id, extraction_id)
    if not extraction or str(extraction.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "EXTRACTION_NOT_FOUND",
                f"Extraction '{extraction_id}' not found in project '{project_id}'",
            ),
        )

    # 2. Check extraction status
    if extraction.status != ExtractionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "EXTRACTION_NOT_COMPLETED",
                f"Extraction is in '{extraction.status.value}' state; matching requires 'completed' extraction",
            ),
        )

    extracted_data = extraction.extracted_data
    activities: list[ExtractedActivity] = []
    if isinstance(extracted_data, dict):
        raw_list = extracted_data.get("extracted_activities", [])
        activities = [ExtractedActivity(**a) if isinstance(a, dict) else a for a in raw_list]
    elif extracted_data is not None and hasattr(extracted_data, "extracted_activities"):
        activities = extracted_data.extracted_activities

    if not activities:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_error_response(
                "NO_EXTRACTED_ACTIVITIES",
                "Extraction does not contain any extracted physical activities to match",
            ),
        )

    # 3. Match each extracted activity and persist recommendations
    persisted_matches: list[MatchRecommendationResponse] = []

    try:
        ext_uuid = UUID(extraction_id)
        for idx, act in enumerate(activities):
            recommendation = await matching_service.match_extracted_activity(
                project_id=project_id,
                activity=act,
                extraction_id=ext_uuid,
                activity_index=idx,
            )

            # Persist to public.ai_matches via repository
            persisted = await matching_service.repository.upsert_match(recommendation)
            persisted_matches.append(persisted)

        return MatchRecommendationListResponse(
            items=persisted_matches,
            total=len(persisted_matches),
        )

    except NoCandidatesError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("NO_SCHEDULE_CANDIDATES", str(err)),
        )
    except CrossProjectCandidateError as err:
        logger.error(f"Tenant violation detected during matching: {err}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response("TENANT_VIOLATION", "Cross-project candidate match rejected"),
        )
    except Exception as err:
        logger.error(f"Schedule matching failed for extraction '{extraction_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("MATCHING_FAILED", "Schedule matching execution failed"),
        )


@router.get(
    "/extractions/{extraction_id}/matches",
    response_model=MatchRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get match recommendations for an extraction",
)
async def get_extraction_matches(
    project_id: str,
    extraction_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> MatchRecommendationListResponse:
    """
    Retrieves stored match recommendations for an extraction.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    # Verify extraction belongs to project
    extraction = await extraction_service.get_extraction(project_id, extraction_id)
    if not extraction or str(extraction.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "EXTRACTION_NOT_FOUND",
                f"Extraction '{extraction_id}' not found in project '{project_id}'",
            ),
        )

    try:
        matches = await matching_service.repository.list_matches(
            project_id=project_id,
            extraction_id=extraction_id,
        )
        return MatchRecommendationListResponse(
            items=matches,
            total=len(matches),
        )
    except Exception as err:
        logger.error(f"Failed to query matches for extraction '{extraction_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve match recommendations"),
        )
