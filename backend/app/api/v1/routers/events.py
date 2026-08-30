"""
Field Events API Router — SiteSync AI Phase 3.
Provides secure endpoints for project-scoped field events.
Endpoints:
  - GET    /api/v1/projects/{project_id}/events
  - GET    /api/v1/projects/{project_id}/events/{event_id}
  - POST   /api/v1/projects/{project_id}/events
  - PATCH  /api/v1/projects/{project_id}/events/{event_id}
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.events import (
    FieldEventCreate,
    FieldEventListResponse,
    FieldEventResponse,
    FieldEventUpdate,
)
from app.services.event_service import event_service

router = APIRouter(prefix="/projects/{project_id}/events", tags=["events"])


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


@router.get("", response_model=FieldEventListResponse, summary="List project field events")
async def list_events(
    project_id: str,
    report_id: Optional[str] = Query(default=None, description="Filter events by source report"),
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldEventListResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    return event_service.list_events(project_id=project_id, report_id=report_id)


@router.get("/{event_id}", response_model=FieldEventResponse, summary="Get field event by ID")
async def get_event(
    project_id: str,
    event_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldEventResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    event = event_service.get_event(project_id, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EVENT_NOT_FOUND", f"Field event '{event_id}' not found in project '{project_id}'"),
        )
    return event


@router.post(
    "",
    response_model=FieldEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new field event",
)
async def create_event(
    project_id: str,
    payload: FieldEventCreate,
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldEventResponse:
    # Requires SUPERVISOR role or above
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)
    return event_service.create_event(
        project_id=project_id,
        data=payload,
        extracted_by_id=current_user.id,
    )


@router.patch(
    "/{event_id}",
    response_model=FieldEventResponse,
    summary="Update a field event",
)
async def update_event(
    project_id: str,
    event_id: str,
    payload: FieldEventUpdate,
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldEventResponse:
    # Requires PLANNER role or above
    _verify_membership(project_id, current_user, min_role=ProjectRole.PLANNER)
    updated = event_service.update_event(project_id, event_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EVENT_NOT_FOUND", f"Field event '{event_id}' not found in project '{project_id}'"),
        )
    return updated
