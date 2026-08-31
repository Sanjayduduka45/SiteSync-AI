"""v1 API router — aggregates all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers import (
    audit,
    auth,
    decisions,
    events,
    exports,
    extractions,
    health,
    inputs,
    network,
    reports,
    risks,
    schedules,
    variance,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(reports.router)
router.include_router(events.router)
router.include_router(inputs.router)
router.include_router(extractions.router)
router.include_router(schedules.router)
router.include_router(decisions.router)
router.include_router(variance.router)
router.include_router(network.router)
router.include_router(risks.router)
router.include_router(audit.router)
router.include_router(exports.router)
