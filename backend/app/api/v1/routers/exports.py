"""
SiteSync AI — Phase 10.3 Report Exports API Router.
Provides secure multi-tenant HTTP endpoints for:
  - Exporting complete project datasets in RFC 4180-compliant CSV format with formula injection escaping (Viewer+)
  - Exporting complete project datasets in structured JSON format (Viewer+)

Tenant containment and RBAC:
  - project_id is strictly derived from the URL path.
  - All endpoints permit VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
  - Full dataset export semantics: exports entire dataset without accidental UI pagination slicing.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.export import ExportDatasetType, ExportFormat
from app.services.report_export_service import (
    CrossProjectExportError,
    UnsupportedExportDatasetError,
    UnsupportedExportFormatError,
    report_export_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["exports"])


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
# Export Dataset Endpoint
# ==============================================================================

@router.get(
    "/{dataset}",
    status_code=status.HTTP_200_OK,
    summary="Export complete project dataset in CSV or JSON format",
)
async def export_dataset(
    project_id: str,
    dataset: str,
    format: str = Query("csv", description="Export format: 'csv' or 'json'"),
    current_user: UserIdentity = Depends(get_current_user),
) -> Response:
    """
    Exports full project dataset (approved_actuals, variance, or risk_register) in CSV or JSON format.
    CSV exports apply RFC 4180 rules and formula injection escaping.
    JSON exports emit structured envelope JSON.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        export_result = await report_export_service.export_dataset(
            project_id=project_id,
            dataset_type=dataset,
            export_format=format,
        )

        headers = {
            "Content-Disposition": f'attachment; filename="{export_result.filename}"',
        }

        return Response(
            content=export_result.data,
            media_type=export_result.content_type,
            headers=headers,
            status_code=status.HTTP_200_OK,
        )
    except UnsupportedExportDatasetError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DATASET", str(err)),
        )
    except UnsupportedExportFormatError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_FORMAT", str(err)),
        )
    except CrossProjectExportError as err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response("CROSS_PROJECT_EXPORT_DENIED", str(err)),
        )
    except Exception as err:
        logger.error(
            f"Failed to export dataset '{dataset}' (format '{format}') for project '{project_id}': {err}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to generate export"),
        )
