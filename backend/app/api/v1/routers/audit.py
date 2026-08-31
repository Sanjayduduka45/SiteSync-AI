"""
SiteSync AI — Phase 10.3 Audit & Provenance API Router.
Provides secure multi-tenant HTTP endpoints for:
  - Querying immutable audit event streams with server-side filters and deterministic ordering (Viewer+)
  - Resolving complete field-to-schedule provenance lineage graphs (Viewer+)

Tenant containment and RBAC:
  - project_id is strictly derived from the URL path.
  - All endpoints permit VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
  - No mutation endpoints exist (audit stream is strictly append-only and read-only).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.audit import (
    AuditEventListResponse,
    AuditEventType,
    AuditFilterParams,
    ProvenanceChain,
    ProvenanceNodeType,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.services.audit_service import (
    AuditEntityNotFoundError,
    CrossProjectAuditError,
    UnsupportedProvenanceEntityTypeError,
    audit_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/audit", tags=["audit"])


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
# Audit Event List Endpoint
# ==============================================================================

@router.get(
    "",
    response_model=AuditEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List deterministic audit events with filtering and pagination",
)
async def list_audit_events(
    project_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    event_type: Optional[AuditEventType] = Query(None, description="Filter by canonical audit event type"),
    entity_type: Optional[str] = Query(None, description="Filter by source entity type"),
    actor_id: Optional[UUID] = Query(None, description="Filter by actor UUID"),
    entity_id: Optional[UUID] = Query(None, description="Filter by entity UUID"),
    start_date: Optional[datetime] = Query(None, description="Filter by minimum event timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter by maximum event timestamp"),
    current_user: UserIdentity = Depends(get_current_user),
) -> AuditEventListResponse:
    """
    Returns paginated audit events sorted deterministically by (timestamp DESC, event_type ASC, entity_id ASC, id ASC).
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    params = AuditFilterParams(
        event_type=event_type,
        entity_type=entity_type,
        actor_id=actor_id,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    try:
        return await audit_service.list_audit_events(project_id=project_id, params=params)
    except Exception as err:
        logger.error(f"Failed to list audit events for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve audit events"),
        )


# ==============================================================================
# Provenance Lineage Graph Endpoint
# ==============================================================================

@router.get(
    "/provenance/{entity_type}/{entity_id}",
    response_model=ProvenanceChain,
    status_code=status.HTTP_200_OK,
    summary="Resolve end-to-end causal provenance lineage graph for an entity",
)
async def get_provenance(
    project_id: str,
    entity_type: str,
    entity_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> ProvenanceChain:
    """
    Constructs the complete upstream and downstream causal provenance chain for a given entity.
    Traces Field Input -> Extraction -> Match Recommendation -> Planner Decision -> Approved Actual -> Variance -> Risk.
    Preserves rejection and modification states accurately without hallucinating missing links.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        return await audit_service.resolve_provenance(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except UnsupportedProvenanceEntityTypeError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_ENTITY_TYPE", str(err)),
        )
    except (AuditEntityNotFoundError, CrossProjectAuditError) as err:
        # Cross-project requests do not leak entity existence across tenant boundaries
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("ENTITY_NOT_FOUND", str(err)),
        )
    except Exception as err:
        logger.error(
            f"Failed to resolve provenance for entity '{entity_type}/{entity_id}' in project '{project_id}': {err}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to resolve provenance graph"),
        )
