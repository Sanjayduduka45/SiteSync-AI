"""
SiteSync AI — Phase 8.2 Variance Query Service.
Coordinates read-only project-scoped data access for:
  - public.schedule_activities
  - public.approved_actuals
and delegates all variance math, aggregation, and status classification
to the pure Phase 8.1 VarianceService.
Strictly read-only, multi-tenant contained, and free of Phase 9 concepts.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Optional
from uuid import UUID

from app.schemas.variance import (
    ActivityVarianceInput,
    ActivityVarianceItem,
    ApprovedActualInput,
    ProjectVarianceSummary,
    WbsRollup,
)
from app.services.decision_service import decision_service
from app.services.schedule_service import schedule_service
from app.services.variance_service import variance_service

logger = logging.getLogger(__name__)


def _parse_uuid(val: str | UUID) -> UUID:
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


class VarianceQueryService:
    """
    Read-only query service for Plan vs Actual variance metrics.
    Retrieves baseline schedule activities and approved actuals for an authorized project,
    constructs domain inputs, and computes deterministic variance outputs.
    """

    def __init__(self) -> None:
        self.schedule_service = schedule_service
        self.decision_service = decision_service
        self.variance_engine = variance_service

    async def _get_calculated_activity_items(
        self,
        project_id: str | UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[ActivityVarianceItem]:
        """
        Retrieves all schedule activities and approved actuals scoped to project_id,
        and computes ActivityVarianceItem results for each activity.
        """
        proj_str = str(project_id)
        proj_uuid = _parse_uuid(project_id)

        # 1. Bulk retrieve schedule activities for project
        activities_resp = await self.schedule_service.list_activities(
            project_id=proj_str,
            limit=10000,
            offset=0,
        )
        activities = activities_resp.items

        # 2. Bulk retrieve approved actuals for project
        actual_records, _ = await self.decision_service.actual_repo.list_approved_actuals(
            project_id=proj_str,
            from_date=from_date,
            to_date=to_date,
            limit=10000,
            offset=0,
        )


        # 3. Group approved actuals by schedule_activity_id
        actuals_by_activity: dict[str, list[ApprovedActualInput]] = defaultdict(list)
        for act in actual_records:
            actuals_by_activity[str(act.schedule_activity_id)].append(
                ApprovedActualInput(
                    actual_quantity=act.actual_quantity,
                    actual_unit=act.actual_unit,
                    actual_date=act.actual_date,
                )
            )

        # 4. Compute variance for each activity via Phase 8.1 pure engine
        calculated_items: list[ActivityVarianceItem] = []
        for act in activities:
            inp = ActivityVarianceInput(
                activity_id=act.id,
                project_id=proj_uuid,
                activity_code=act.activity_code,
                name=act.name,
                wbs_code=act.wbs_code,
                discipline=act.discipline,
                location=act.location,
                planned_quantity=act.planned_quantity,
                planned_unit=act.planned_unit,
                planned_start_date=act.planned_start_date,
                planned_finish_date=act.planned_finish_date,
                approved_actuals=actuals_by_activity.get(str(act.id), []),
            )
            item_result = self.variance_engine.calculate_activity_variance(inp)
            calculated_items.append(item_result)

        return calculated_items

    async def list_activity_variances(
        self,
        project_id: str | UUID,
        limit: int = 50,
        offset: int = 0,
        wbs_code: Optional[str] = None,
        discipline: Optional[str] = None,
        variance_status: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> tuple[list[ActivityVarianceItem], int]:
        """
        Lists paginated activity-level variance items with optional filters.
        """
        items = await self._get_calculated_activity_items(
            project_id=project_id,
            from_date=from_date,
            to_date=to_date,
        )

        filtered: list[ActivityVarianceItem] = []
        for item in items:
            if wbs_code is not None:
                if (item.wbs_code or "").strip() != wbs_code.strip():
                    continue

            if discipline is not None:
                if (item.discipline or "").strip().lower() != discipline.strip().lower():
                    continue

            if variance_status is not None:
                if item.variance_status.value != variance_status:
                    continue

            filtered.append(item)

        # Stable deterministic sort: activity_code ASC, activity_id ASC
        filtered.sort(key=lambda x: (x.activity_code, str(x.activity_id)))

        total = len(filtered)
        sliced = filtered[offset : offset + limit]
        return sliced, total

    async def get_project_summary(
        self,
        project_id: str | UUID,
    ) -> ProjectVarianceSummary:
        """
        Calculates project-wide variance KPIs and homogeneous unit rollups.
        """
        proj_uuid = _parse_uuid(project_id)
        items = await self._get_calculated_activity_items(project_id=project_id)
        return self.variance_engine.calculate_project_summary(proj_uuid, items)

    async def get_wbs_rollups(
        self,
        project_id: str | UUID,
    ) -> list[WbsRollup]:
        """
        Calculates WBS tier rollups across homogeneous units.
        """
        items = await self._get_calculated_activity_items(project_id=project_id)
        return self.variance_engine.calculate_wbs_rollups(items)

    async def get_activity_variance(
        self,
        project_id: str | UUID,
        activity_id: str | UUID,
    ) -> Optional[ActivityVarianceItem]:
        """
        Calculates and returns variance metrics for a single schedule activity.
        """
        act_uuid = _parse_uuid(activity_id)
        items = await self._get_calculated_activity_items(project_id=project_id)
        for item in items:
            if item.activity_id == act_uuid:
                return item
        return None


variance_query_service = VarianceQueryService()
