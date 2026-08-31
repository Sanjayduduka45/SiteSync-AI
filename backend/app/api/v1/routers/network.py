"""
SiteSync AI — Phase 9.5 Dependency Network & Critical Path API Router.
Provides secure multi-tenant HTTP endpoints for:
  - Listing schedule dependency edges (Viewer+)
  - Creating schedule dependency edges with cycle validation (Planner/Admin)
  - Deleting schedule dependency edges (Admin only)
  - Computing and retrieving Critical Path Method (CPM) metrics (Viewer+)

Tenant containment and RBAC:
  - project_id is strictly derived from the URL path.
  - POST /network/dependencies requires PLANNER or ADMIN role.
  - DELETE /network/dependencies/{dependency_id} requires ADMIN role.
  - All GET endpoints permit VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
  - All domain graph and CPM calculations delegate to pure domain services.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import (
    create_error_response,
    get_current_user,
    membership_registry,
)
from app.schemas.auth import ProjectRole, UserIdentity, has_minimum_role
from app.schemas.network import (
    CriticalPathResponse,
    DependencyCreate,
    DependencyListResponse,
    DependencyResponse,
)
from app.services.cpm_service import CPMGraphCycleError, CPMValidationError
from app.services.dependency_service import (
    DependencyActivityNotFoundError,
    DependencyCycleError,
    DependencyDuplicateError,
    DependencyNotFoundError,
    DependencyValidationError,
    dependency_service,
)
from app.services.risk_query_service import risk_query_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/network", tags=["network"])


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
# Schedule Dependencies Endpoints
# ==============================================================================

@router.get(
    "/dependencies",
    response_model=DependencyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all schedule dependency edges for a project",
)
async def list_dependencies(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> DependencyListResponse:
    """
    Returns all directed dependency relationships scoped to project_id.
    Sorted deterministically by predecessor_id ASC, successor_id ASC, id ASC.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        items = await dependency_service.list_dependencies(project_id=project_id)
        return DependencyListResponse(
            items=items,
            total=len(items),
        )
    except Exception as err:
        logger.error(f"Failed to list dependencies for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to retrieve schedule dependencies"),
        )


@router.post(
    "/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new schedule dependency edge with cycle detection",
)
async def create_dependency(
    project_id: str,
    data: DependencyCreate,
    current_user: UserIdentity = Depends(get_current_user),
) -> DependencyResponse:
    """
    Creates a new directed dependency relationship between two activities in the same project.
    Validates predecessor/successor existence, self-loop prevention, duplicate prevention,
    and executes topological sort cycle check before committing.
    Requires PLANNER or ADMIN role.
    """
    _verify_membership(project_id, current_user, ProjectRole.PLANNER)

    try:
        created = await dependency_service.create_dependency(
            project_id=project_id,
            data=data,
        )
        return created
    except DependencyActivityNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("ACTIVITY_NOT_FOUND", str(err)),
        )
    except (DependencyCycleError, CPMGraphCycleError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("CYCLE_DETECTED", "Dependency cycle detected."),
        )
    except DependencyDuplicateError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("DUPLICATE_DEPENDENCY", str(err)),
        )
    except (DependencyValidationError, CPMValidationError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response("INVALID_DEPENDENCY", str(err)),
        )
    except Exception as err:
        logger.error(f"Unexpected error creating dependency for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to create schedule dependency"),
        )


@router.delete(
    "/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a schedule dependency edge",
)
async def delete_dependency(
    project_id: str,
    dependency_id: str,
    current_user: UserIdentity = Depends(get_current_user),
):
    """
    Deletes an existing schedule dependency relationship.
    Strictly scoped to project_id; cross-project deletion is prevented.
    Requires ADMIN role only.
    """
    _verify_membership(project_id, current_user, ProjectRole.ADMIN)

    try:
        await dependency_service.delete_dependency(
            project_id=project_id,
            dependency_id=dependency_id,
        )
        return None
    except DependencyNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response("DEPENDENCY_NOT_FOUND", str(err)),
        )
    except Exception as err:
        logger.error(f"Unexpected error deleting dependency '{dependency_id}' in project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to delete schedule dependency"),
        )


# ==============================================================================
# Critical Path Method (CPM) Endpoint
# ==============================================================================

@router.get(
    "/critical-path",
    response_model=CriticalPathResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate and return project Critical Path Method (CPM) metrics",
)
async def get_critical_path(
    project_id: str,
    current_user: UserIdentity = Depends(get_current_user),
) -> CriticalPathResponse:
    """
    Computes Critical Path Method forward/backward pass on baseline activities and dependencies.
    Returns early/late dates, total float, free float, and critical path activity sequences.
    Accessible by VIEWER, SUPERVISOR, PLANNER, and ADMIN roles.
    """
    _verify_membership(project_id, current_user, ProjectRole.VIEWER)

    try:
        result = await risk_query_service.get_critical_path(project_id=project_id)
        return result
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
        logger.error(f"Unexpected error computing critical path for project '{project_id}': {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response("INTERNAL_ERROR", "Failed to compute critical path"),
        )
