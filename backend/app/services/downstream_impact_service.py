"""
SiteSync AI — Phase 9.3 Downstream Impact & Float Erosion Pure Domain Engine.
Stateless, database-agnostic business logic implementing:
  - Transitive directed acyclic subgraph traversal from delayed source activity (ADR-016)
  - Deduplication of multi-path reachable successor activities
  - Factual schedule delay propagation vs buffer absorption
  - Float erosion quantification and critical slippage classification
  - Completed successor activity historical exclusion
  - Deterministic traversal path and depth tracking
"""

from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID

from app.schemas.cpm import (
    CPMDependencyInput,
    CPMNetworkResult,
    DependencyRelationshipType,
)
from app.schemas.downstream_impact import (
    DownstreamImpactResult,
    DownstreamImpactSeverity,
    ImpactedSuccessorNode,
)
from app.services.cpm_service import CPMValidationError


class DownstreamImpactService:
    """
    Pure domain service for schedule network downstream impact analysis.
    Consumes Phase 9.2 CPM outputs without recalculating CPM baseline.
    """

    @staticmethod
    def calculate_downstream_impact(
        cpm_result: CPMNetworkResult,
        dependencies: list[CPMDependencyInput],
        source_activity_id: UUID,
        factual_delay_days: int = 0,
        completed_activity_ids: set[UUID] | None = None,
    ) -> DownstreamImpactResult:
        """
        Evaluates the full transitive downstream impact of a factual schedule delay.
        Strictly follows ADR-016.
        """
        # 1. Locate source activity in pre-computed CPM result
        node_map = {node.activity_id: node for node in cpm_result.nodes}
        if source_activity_id not in node_map:
            raise CPMValidationError(
                f"Source activity {source_activity_id} not found in supplied CPM network result"
            )

        source_node = node_map[source_activity_id]
        completed_set = completed_activity_ids or set()

        # 2. Build outgoing dependency adjacency mapping
        outgoing_edges: dict[UUID, list[CPMDependencyInput]] = defaultdict(list)
        for dep in dependencies:
            if dep.project_id != cpm_result.project_id:
                raise CPMValidationError(
                    f"Cross-project dependency detected: expected project {cpm_result.project_id}, got {dep.project_id}"
                )
            outgoing_edges[dep.predecessor_id].append(dep)

        # 3. Transitive BFS traversal with shortest-hop depth and path tracking
        # Queue item: (current_act_id, depth, path, rel_type, lag)
        queue: deque[tuple[UUID, int, list[str], DependencyRelationshipType | None, int]] = deque()

        # Seed direct successors of source activity
        # Sort outgoing edges deterministically for stable exploration
        sorted_seed_edges = sorted(
            outgoing_edges[source_activity_id],
            key=lambda d: (node_map[d.successor_id].activity_code if d.successor_id in node_map else "", str(d.successor_id)),
        )

        for dep in sorted_seed_edges:
            succ_id = dep.successor_id
            if succ_id in node_map:
                succ_code = node_map[succ_id].activity_code
                queue.append((
                    succ_id,
                    1,
                    [source_node.activity_code, succ_code],
                    dep.relationship_type,
                    dep.lag_days,
                ))

        # Best-known exploration state: act_id -> (depth, path, rel_type, lag)
        visited_info: dict[UUID, tuple[int, list[str], DependencyRelationshipType | None, int]] = {}

        while queue:
            curr_id, depth, path, rel_type, lag = queue.popleft()

            if curr_id not in visited_info or depth < visited_info[curr_id][0]:
                visited_info[curr_id] = (depth, path, rel_type, lag)

                # Explore downstream successors of curr_id
                sorted_next_edges = sorted(
                    outgoing_edges[curr_id],
                    key=lambda d: (node_map[d.successor_id].activity_code if d.successor_id in node_map else "", str(d.successor_id)),
                )

                for next_dep in sorted_next_edges:
                    next_id = next_dep.successor_id
                    if next_id in node_map:
                        next_code = node_map[next_id].activity_code
                        queue.append((
                            next_id,
                            depth + 1,
                            path + [next_code],
                            next_dep.relationship_type,
                            next_dep.lag_days,
                        ))

        # 4. Construct impacted successor records
        impacted_nodes: list[ImpactedSuccessorNode] = []

        for succ_id, (depth, path, rel_type, lag) in visited_info.items():
            succ_node = node_map[succ_id]
            is_completed = succ_id in completed_set
            available_tf = succ_node.total_float

            if is_completed:
                severity = DownstreamImpactSeverity.HISTORICAL_COMPLETED
                float_consumed = 0
                projected_delay = 0
            elif factual_delay_days <= 0:
                severity = DownstreamImpactSeverity.UNAFFECTED
                float_consumed = 0
                projected_delay = 0
            else:
                tf_val = available_tf if available_tf is not None else 0
                if tf_val >= factual_delay_days:
                    severity = DownstreamImpactSeverity.BUFFER_ABSORBED
                    float_consumed = factual_delay_days
                    projected_delay = 0
                else:
                    severity = DownstreamImpactSeverity.CRITICAL_SLIPPAGE
                    float_consumed = max(0, tf_val)
                    projected_delay = factual_delay_days - max(0, tf_val)

            impacted_nodes.append(
                ImpactedSuccessorNode(
                    activity_id=succ_node.activity_id,
                    activity_code=succ_node.activity_code,
                    name=succ_node.name,
                    wbs_code=succ_node.wbs_code,
                    discipline=succ_node.discipline,
                    depth=depth,
                    path=path,
                    relationship_with_immediate_predecessor=rel_type,
                    lag_days_with_immediate_predecessor=lag,
                    planned_start_date=succ_node.planned_start_date,
                    planned_finish_date=succ_node.planned_finish_date,
                    total_float=succ_node.total_float,
                    free_float=succ_node.free_float,
                    is_critical=succ_node.is_critical,
                    is_completed=is_completed,
                    impact_severity=severity,
                    available_float=available_tf,
                    float_consumed=float_consumed,
                    projected_delay_days=projected_delay,
                )
            )

        # 5. Deterministic sorting by depth ASC, activity_code ASC, activity_id ASC
        impacted_nodes.sort(key=lambda n: (n.depth, n.activity_code, str(n.activity_id)))

        # 6. Aggregate severity counts
        critical_count = sum(
            1 for n in impacted_nodes if n.impact_severity == DownstreamImpactSeverity.CRITICAL_SLIPPAGE
        )
        absorbed_count = sum(
            1 for n in impacted_nodes if n.impact_severity == DownstreamImpactSeverity.BUFFER_ABSORBED
        )
        historical_count = sum(
            1 for n in impacted_nodes if n.impact_severity == DownstreamImpactSeverity.HISTORICAL_COMPLETED
        )

        return DownstreamImpactResult(
            project_id=cpm_result.project_id,
            source_activity_id=source_node.activity_id,
            source_activity_code=source_node.activity_code,
            source_name=source_node.name,
            source_delay_days=factual_delay_days,
            is_source_critical=source_node.is_critical,
            total_downstream_activities_count=len(impacted_nodes),
            critical_slippage_count=critical_count,
            buffer_absorbed_count=absorbed_count,
            historical_completed_count=historical_count,
            impacted_successors=impacted_nodes,
        )


downstream_impact_service = DownstreamImpactService()
