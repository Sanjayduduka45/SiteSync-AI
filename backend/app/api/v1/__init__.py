"""v1 API router — aggregates all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import auth, events, health, inputs, reports

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(reports.router)
router.include_router(events.router)
router.include_router(inputs.router)
