"""Health check router — GET /api/v1/health"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Backend health check")
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Returns the operational status of the backend.
    No authentication required — this endpoint is public.
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
    )
