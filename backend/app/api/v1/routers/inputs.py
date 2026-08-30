"""
Field Inputs API Router — SiteSync AI Phase 4.
Provides secure multi-tenant endpoints for raw field progress submissions (text, voice, photo, document).
Endpoints:
  - POST   /api/v1/projects/{project_id}/inputs/text
  - GET    /api/v1/projects/{project_id}/inputs
  - GET    /api/v1/projects/{project_id}/inputs/{input_id}
  - POST   /api/v1/projects/{project_id}/inputs/upload
  - DELETE /api/v1/projects/{project_id}/inputs/{input_id}
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.inputs import (
    FieldInputListResponse,
    FieldInputResponse,
    FieldInputType,
    TextInputCreate,
)
from app.services.input_service import input_service

router = APIRouter(prefix="/projects/{project_id}/inputs", tags=["field-inputs"])


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


@router.post(
    "/text",
    response_model=FieldInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a raw text note from the field",
)
async def create_text_input(
    project_id: str,
    payload: TextInputCreate,
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldInputResponse:
    # Requires SUPERVISOR role or above
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)

    if not payload.raw_text or not payload.raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_error_response("INVALID_CONTENT", "Text input cannot be empty"),
        )

    return input_service.create_text_input(
        project_id=project_id,
        data=payload,
        submitted_by_id=current_user.id,
        submitted_by_email=current_user.email,
    )


@router.get(
    "",
    response_model=FieldInputListResponse,
    summary="List raw field inputs for a project",
)
async def list_inputs(
    project_id: str,
    input_type: Optional[FieldInputType] = Query(default=None, description="Filter by input modality"),
    field_date: Optional[date] = Query(default=None, description="Filter by specific field date"),
    limit: int = Query(default=50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldInputListResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    return input_service.list_inputs(
        project_id=project_id,
        input_type=input_type,
        field_date=field_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{input_id}",
    response_model=FieldInputResponse,
    summary="Get single field input by ID",
)
async def get_input(
    project_id: str,
    input_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldInputResponse:
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)
    inp = input_service.get_input(project_id, input_id)
    if not inp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{input_id}' not found in project '{project_id}'"),
        )
    return inp


@router.post(
    "/upload",
    response_model=FieldInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload voice recording, photo, or document field input",
)
async def upload_media_input(
    project_id: str,
    file: UploadFile = File(..., description="Uploaded media binary"),
    input_type: FieldInputType = Form(..., description="Modality: voice, photo, or document"),
    title: Optional[str] = Form(default=None, description="Optional title"),
    raw_text: Optional[str] = Form(default=None, description="Optional text notes"),
    field_date: Optional[date] = Form(default=None, description="Date work occurred"),
    current_user: UserIdentity = Depends(get_current_user),
) -> FieldInputResponse:
    # Requires SUPERVISOR role or above
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)

    if input_type == FieldInputType.TEXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_ENDPOINT", "Use POST /inputs/text for pure text submissions"),
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("EMPTY_FILE", "Uploaded file is empty"),
        )

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or f"upload_{input_type.value}"

    return await input_service.create_media_input(
        project_id=project_id,
        input_type=input_type,
        filename=filename,
        file_bytes=file_bytes,
        content_type=content_type,
        submitted_by_id=current_user.id,
        submitted_by_email=current_user.email,
        title=title,
        raw_text=raw_text,
        field_date=field_date,
    )


@router.delete(
    "/{input_id}",
    summary="Delete a field input (Admin only)",
)
async def delete_input(
    project_id: str,
    input_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> dict[str, str]:
    # Requires ADMIN role
    _verify_membership(project_id, current_user, min_role=ProjectRole.ADMIN)

    deleted = input_service.delete_input(project_id, input_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{input_id}' not found in project '{project_id}'"),
        )
    return {"status": "deleted", "id": input_id}
