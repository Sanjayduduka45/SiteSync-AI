"""
SiteSync AI — Phase 9.5 Risk & Critical Path Query Orchestration Service.
Coordinates read-only data access across:
  - Phase 6 schedule baseline activities (`public.schedule_activities`)
  - Phase 7/8 approved actuals (`public.approved_actuals`)
  - Phase 9.1 schedule dependencies (`public.schedule_dependencies`)
Delegates all pure domain calculations to:
  - Phase 8.1 VarianceService (via VarianceQueryService)
  - Phase 9.2 CPMService
  - Phase 9.3 DownstreamImpactService
  - Phase 9.4 RiskService
Strictly preserves tenant boundaries and deterministic sorting.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional
from uuid import UUID

from app.schemas.cpm import (
    CPMActivityInput,
    CPMDependencyInput,
    CPMNetworkResult,
)
from app.schemas.downstream_impact import DownstreamImpactResult
from app.schemas.network import (
    CPMActivityNodeResponse,
    CriticalPathResponse,
)
from app.schemas.risk import (
    ActivityRiskAssessment,
    ProjectRiskSummary,
    RiskCategory,
    RiskSeverityLevel,
)
from app.schemas.variance import ActivityVarianceItem, ActivityVarianceStatus
from app.services.cpm_service import cpm_service
from app.services.dependency_service import dependency_service
from app.services.downstream_impact_service import downstream_impact_service
from app.services.risk_service import risk_service
from app.services.schedule_service import schedule_service
from app.services.variance_query_service import variance_query_service

logger = logging.getLogger(__name__)


def _parse_uuid(val: str | UUID) -> UUID:
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


class RiskActivityNotFoundError(Exception):
    """Raised when a requested schedule activity does not exist or does not belong to the project."""
    pass


class RiskQueryService:
    """
    Orchestration service for Schedule Dependencies, Critical Path, and Risk Intelligence.
    Coordinates underlying domain services without recalculating domain mathematics in the router.
    """

    def __init__(self) -> None:
        self.schedule_service = schedule_service
        self.dependency_service = dependency_service
        self.variance_query_service = variance_query_service
        self.cpm_service = cpm_service
        self.downstream_impact_service = downstream_impact_service
        self.risk_service = risk_service

    async def get_critical_path(self, project_id: str | UUID) -> CriticalPathResponse:
        """
        Loads baseline activities and dependency edges, executes Phase 9.2 CPM forward/backward pass,
        and returns deterministic Critical Path metrics.
        """
        proj_str = str(project_id)
        proj_uuid = _parse_uuid(project_id)

        # 1. Load activities
        activities_resp = await self.schedule_service.list_activities(
            project_id=proj_str,
            limit=10000,
            offset=0,
        )
        cpm_activities = [
            CPMActivityInput(
                activity_id=act.id,
                project_id=proj_uuid,
                activity_code=act.activity_code,
                name=act.name,
                wbs_code=act.wbs_code,
                discipline=act.discipline,
                location=act.location,
                planned_start_date=act.planned_start_date,
                planned_finish_date=act.planned_finish_date,
            )
            for act in activities_resp.items
        ]

        # 2. Load dependencies
        dependencies_resp = await self.dependency_service.list_dependencies(project_id=proj_str)
        cpm_dependencies = [
            CPMDependencyInput(
                dependency_id=dep.id,
                project_id=proj_uuid,
                predecessor_id=dep.predecessor_id,
                successor_id=dep.successor_id,
                relationship_type=dep.relationship_type,
                lag_days=dep.lag_days,
            )
            for dep in dependencies_resp
        ]

        # 3. Execute pure CPM forward/backward pass
        cpm_result: CPMNetworkResult = self.cpm_service.calculate_cpm(
            activities=cpm_activities,
            dependencies=cpm_dependencies,
            project_id=proj_uuid,
        )

        # 4. Map to response model
        activity_node_responses = [
            CPMActivityNodeResponse(
                activity_id=node.activity_id,
                project_id=node.project_id,
                activity_code=node.activity_code,
                name=node.name,
                wbs_code=node.wbs_code,
                discipline=node.discipline,
                location=node.location,
                planned_start_date=node.planned_start_date,
                planned_finish_date=node.planned_finish_date,
                duration_days=node.duration_days,
                early_start=node.early_start,
                early_finish=node.early_finish,
                late_start=node.late_start,
                late_finish=node.late_finish,
                total_float_days=node.total_float,
                free_float_days=node.free_float,
                is_critical=node.is_critical,
            )
            for node in cpm_result.nodes
        ]

        return CriticalPathResponse(
            project_id=proj_uuid,
            project_start_date=cpm_result.project_start_date,
            project_finish_date=cpm_result.project_finish_date,
            total_activities=cpm_result.total_activities,
            critical_activities_count=cpm_result.critical_activities_count,
            critical_path_activity_ids=cpm_result.critical_path,
            activities=activity_node_responses,
        )

    async def get_project_risk_summary(self, project_id: str | UUID) -> ProjectRiskSummary:
        """
        Orchestrates Phase 8 verified variance, Phase 9.2 CPM, Phase 9.3 downstream impact,
        and Phase 9.4 risk intelligence engine.
        """
        proj_str = str(project_id)
        proj_uuid = _parse_uuid(project_id)

        # 1. Load activities
        activities_resp = await self.schedule_service.list_activities(
            project_id=proj_str,
            limit=10000,
            offset=0,
        )
        cpm_activities = [
            CPMActivityInput(
                activity_id=act.id,
                project_id=proj_uuid,
                activity_code=act.activity_code,
                name=act.name,
                wbs_code=act.wbs_code,
                discipline=act.discipline,
                location=act.location,
                planned_start_date=act.planned_start_date,
                planned_finish_date=act.planned_finish_date,
            )
            for act in activities_resp.items
        ]

        # 2. Load dependencies
        dependencies_resp = await self.dependency_service.list_dependencies(project_id=proj_str)
        cpm_dependencies = [
            CPMDependencyInput(
                dependency_id=dep.id,
                project_id=proj_uuid,
                predecessor_id=dep.predecessor_id,
                successor_id=dep.successor_id,
                relationship_type=dep.relationship_type,
                lag_days=dep.lag_days,
            )
            for dep in dependencies_resp
        ]

        # 3. Calculate CPM baseline
        cpm_result: CPMNetworkResult = self.cpm_service.calculate_cpm(
            activities=cpm_activities,
            dependencies=cpm_dependencies,
            project_id=proj_uuid,
        )

        # 4. Load Phase 8 verified variance items
        variance_items = await self.variance_query_service._get_calculated_activity_items(
            project_id=proj_str
        )
        variance_map = {item.activity_id: item for item in variance_items}

        # 5. Extract completed activity IDs from Phase 8 verified actuals
        completed_activity_ids = {
            item.activity_id
            for item in variance_items
            if item.variance_status == ActivityVarianceStatus.COMPLETED
        }

        # 6. Direct successors mapping
        direct_successors_count: dict[UUID, int] = defaultdict(int)
        for dep in cpm_dependencies:
            direct_successors_count[dep.predecessor_id] += 1

        # 7. Calculate downstream impact for each activity
        downstream_impact_map: dict[UUID, DownstreamImpactResult] = {}
        for node in cpm_result.nodes:
            v_item = variance_map.get(node.activity_id)
            d_var = v_item.date_variance_days if v_item and v_item.date_variance_days is not None else 0
            factual_delay = max(0, d_var)

            impact_result = self.downstream_impact_service.calculate_downstream_impact(
                cpm_result=cpm_result,
                dependencies=cpm_dependencies,
                source_activity_id=node.activity_id,
                factual_delay_days=factual_delay,
                completed_activity_ids=completed_activity_ids,
            )
            downstream_impact_map[node.activity_id] = impact_result

        # 8. Assess project risks via Phase 9.4 RiskService
        summary = self.risk_service.assess_project_risks(
            cpm_result=cpm_result,
            variance_items=variance_items,
            downstream_impact_map=downstream_impact_map,
            direct_successors_count_map=dict(direct_successors_count),
        )

        return summary

    async def list_risk_activities(
        self,
        project_id: str | UUID,
        severity: Optional[RiskSeverityLevel] = None,
        category: Optional[RiskCategory] = None,
        wbs_code: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActivityRiskAssessment], int]:
        """
        Retrieves assessed activity risk register with server-side filtering,
        deterministic sorting, and pagination.
        """
        summary = await self.get_project_risk_summary(project_id=project_id)
        all_items = summary.items

        filtered: list[ActivityRiskAssessment] = []
        for item in all_items:
            if severity is not None and item.severity != severity:
                continue

            if category is not None and category not in item.categories:
                continue

            if wbs_code is not None and (item.wbs_code or "").strip() != wbs_code.strip():
                continue

            if discipline is not None and (item.discipline or "").strip().lower() != discipline.strip().lower():
                continue

            filtered.append(item)

        total = len(filtered)
        sliced = filtered[offset : offset + limit]
        return sliced, total

    async def get_downstream_impact(
        self,
        project_id: str | UUID,
        activity_id: str | UUID,
    ) -> DownstreamImpactResult:
        """
        Evaluates full transitive downstream impact for a specific schedule activity.
        Validates activity belongs to project, uses pre-computed Phase 9.2 CPM and Phase 8 verified actuals.
        """
        proj_str = str(project_id)
        act_uuid = _parse_uuid(activity_id)
        proj_uuid = _parse_uuid(project_id)

        # 1. Verify activity exists and belongs to project
        act = await self.schedule_service.get_activity(proj_str, str(act_uuid))
        if not act or act.project_id != proj_uuid:
            raise RiskActivityNotFoundError(
                f"Schedule activity '{act_uuid}' not found in project '{proj_str}'"
            )

        # 2. Load activities
        activities_resp = await self.schedule_service.list_activities(
            project_id=proj_str,
            limit=10000,
            offset=0,
        )
        cpm_activities = [
            CPMActivityInput(
                activity_id=a.id,
                project_id=proj_uuid,
                activity_code=a.activity_code,
                name=a.name,
                wbs_code=a.wbs_code,
                discipline=a.discipline,
                location=a.location,
                planned_start_date=a.planned_start_date,
                planned_finish_date=a.planned_finish_date,
            )
            for a in activities_resp.items
        ]

        # 3. Load dependencies
        dependencies_resp = await self.dependency_service.list_dependencies(project_id=proj_str)
        cpm_dependencies = [
            CPMDependencyInput(
                dependency_id=dep.id,
                project_id=proj_uuid,
                predecessor_id=dep.predecessor_id,
                successor_id=dep.successor_id,
                relationship_type=dep.relationship_type,
                lag_days=dep.lag_days,
            )
            for dep in dependencies_resp
        ]

        # 4. Calculate CPM baseline
        cpm_result: CPMNetworkResult = self.cpm_service.calculate_cpm(
            activities=cpm_activities,
            dependencies=cpm_dependencies,
            project_id=proj_uuid,
        )

        # 5. Load Phase 8 verified variances to get factual delay and completed set
        variance_items = await self.variance_query_service._get_calculated_activity_items(
            project_id=proj_str
        )
        variance_map = {item.activity_id: item for item in variance_items}

        v_item = variance_map.get(act_uuid)
        d_var = v_item.date_variance_days if v_item and v_item.date_variance_days is not None else 0
        factual_delay = max(0, d_var)

        completed_activity_ids = {
            item.activity_id
            for item in variance_items
            if item.variance_status == ActivityVarianceStatus.COMPLETED
        }

        # 6. Execute downstream impact analysis
        return self.downstream_impact_service.calculate_downstream_impact(
            cpm_result=cpm_result,
            dependencies=cpm_dependencies,
            source_activity_id=act_uuid,
            factual_delay_days=factual_delay,
            completed_activity_ids=completed_activity_ids,
        )

    async def get_activity_risk(
        self,
        project_id: str | UUID,
        activity_id: str | UUID,
    ) -> Optional[ActivityRiskAssessment]:
        """
        Assesses and returns risk intelligence for a single schedule activity.
        """
        act_uuid = _parse_uuid(activity_id)
        summary = await self.get_project_risk_summary(project_id=project_id)
        for item in summary.items:
            if item.activity_id == act_uuid:
                return item
        return None


risk_query_service = RiskQueryService()
