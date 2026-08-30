"""v1 API router — aggregates all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import health

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
