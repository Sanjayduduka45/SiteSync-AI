"""
AI Extractions API Router — SiteSync AI Phase 5.
Provides secure multi-tenant endpoints for triggering and retrieving AI-extracted construction progress.

Endpoints:
  - POST /api/v1/projects/{project_id}/inputs/{input_id}/extract
  - GET  /api/v1/projects/{project_id}/inputs/{input_id}/extractions
  - GET  /api/v1/projects/{project_id}/extractions
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.extractions import (
    ExtractionListResponse,
    ExtractionResponse,
    ExtractionStatus,
)
from app.services.extraction_service import (
    CrossProjectInputError,
    EvidenceVerificationError,
    ExtractionInputError,
    ExtractionNotFoundError,
    extraction_service,
)
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiExtractionParseError,
    GeminiProviderError,
    GeminiTimeoutError,
)
from app.services.input_service import input_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["ai-extractions"])


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
    "/inputs/{input_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI extraction for a raw field input",
)
async def trigger_extraction(
    project_id: str,
    input_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ExtractionResponse:
    """
    Triggers structured AI extraction for a specific field input.
    Requires SUPERVISOR role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)

    try:
        return await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=input_id,
        )
    except ExtractionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{input_id}' not found in project '{project_id}'"),
        )
    except CrossProjectInputError:
        # IDOR Defense: do not leak whether input exists in another tenant
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{input_id}' not found in project '{project_id}'"),
        )
    except ExtractionInputError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_INPUT", str(err)),
        )
    except EvidenceVerificationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_error_response("EVIDENCE_VERIFICATION_FAILED", str(err)),
        )
    except (GeminiProviderError, GeminiTimeoutError, GeminiExtractionParseError) as err:
        logger.error(f"AI Provider failure during extraction: {err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=create_error_response("AI_PROVIDER_ERROR", "AI extraction provider encountered a transient error. Please retry."),
        )
    except GeminiConfigurationError as err:
        logger.critical(f"AI Configuration error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "AI processing service is improperly configured."),
        )
    except Exception as err:
        logger.error(f"Unexpected extraction error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "An unexpected error occurred during extraction processing."),
        )



@router.post(
    "/extractions/{extraction_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-run AI extraction for a specific extraction record by ID",
)
async def rerun_extraction_by_id(
    project_id: str,
    extraction_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ExtractionResponse:
    """
    Re-runs structured AI extraction for an existing extraction record by looking up its associated field input.
    Requires SUPERVISOR role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.SUPERVISOR)

    extraction = await extraction_service.get_extraction(project_id, extraction_id)
    if not extraction or str(extraction.project_id) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("EXTRACTION_NOT_FOUND", f"Extraction '{extraction_id}' not found in project '{project_id}'"),
        )

    try:
        return await extraction_service.extract_and_persist(
            project_id=project_id,
            field_input_id=str(extraction.field_input_id),
        )
    except ExtractionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{extraction.field_input_id}' not found in project '{project_id}'"),
        )
    except CrossProjectInputError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{extraction.field_input_id}' not found in project '{project_id}'"),
        )
    except ExtractionInputError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_INPUT", str(err)),
        )
    except EvidenceVerificationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=create_error_response("EVIDENCE_VERIFICATION_FAILED", str(err)),
        )
    except (GeminiProviderError, GeminiTimeoutError, GeminiExtractionParseError) as err:
        logger.error(f"AI Provider failure during re-extraction: {err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=create_error_response("AI_PROVIDER_ERROR", "AI extraction provider encountered a transient error. Please retry."),
        )
    except GeminiConfigurationError as err:
        logger.critical(f"AI Configuration error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "AI processing service is improperly configured."),
        )
    except Exception as err:
        logger.error(f"Unexpected re-extraction error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "An unexpected error occurred during extraction processing."),
        )


@router.get(
    "/inputs/{input_id}/extractions",
    response_model=ExtractionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get extraction records for a specific field input",
)
async def get_input_extractions(
    project_id: str,
    input_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ExtractionListResponse:
    """
    Retrieves the extraction record(s) associated with a single field input.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    # Verify field input exists in this project
    inp = input_service.get_input(project_id, input_id)
    if not inp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("INPUT_NOT_FOUND", f"Field input '{input_id}' not found in project '{project_id}'"),
        )

    extraction = await extraction_service.get_extraction_by_input(project_id, input_id)
    records = [extraction] if extraction else []

    return ExtractionListResponse(
        extractions=records,
        total=len(records),
    )


@router.get(
    "/extractions",
    response_model=ExtractionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all AI extractions for a project",
)
async def list_project_extractions(
    project_id: str,
    status_filter: Optional[ExtractionStatus] = Query(None, alias="status", description="Filter by extraction status"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return (1-100)"),
    offset: int = Query(0, ge=0, description="Offset index for pagination"),
    current_user: UserIdentity = Depends(get_current_user),
) -> ExtractionListResponse:
    """
    Lists all AI extractions for the project with optional status filter and pagination.
    Requires VIEWER role or above.
    """
    _verify_membership(project_id, current_user, min_role=ProjectRole.VIEWER)

    return await extraction_service.list_extractions(
        project_id=project_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
