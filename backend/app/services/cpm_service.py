"""
SiteSync AI — Phase 9.2 Critical Path Method (CPM) Pure Domain Engine.
Stateless, database-agnostic business logic implementing:
  - Directed Acyclic Graph (DAG) validation and cycle detection (ADR-014)
  - Deterministic topological ordering with stable tie-breaking
  - Activity duration derivation from planned date intervals (ADR-015)
  - CPM Forward Pass across PDM relationships (FS, SS, FF, SF) and lag
  - CPM Backward Pass and Project Finish Anchor (ADR-015)
  - Total Float (TF) and Free Float (FF) calculations (ADR-015)
  - Criticality determination (TF <= 0) and Critical Path extraction
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, timedelta
from heapq import heappop, heappush
from uuid import UUID

from app.schemas.cpm import (
    CPMActivityInput,
    CPMActivityNode,
    CPMDependencyInput,
    CPMNetworkResult,
    DependencyRelationshipType,
)


class CPMValidationError(ValueError):
    """Raised when CPM inputs, date ranges, or network topology fail validation."""
    pass


class CPMGraphCycleError(CPMValidationError):
    """Raised when dependency graph contains a directed cycle."""
    pass


def calculate_activity_duration(start_date: date | None, finish_date: date | None) -> int:
    """
    Calculates inclusive calendar-day duration:
      D_i = (planned_finish_date - planned_start_date) + 1 day.
    Returns 0 if either date is None.
    Raises CPMValidationError if finish_date < start_date.
    """
    if start_date is None or finish_date is None:
        return 0
    if finish_date < start_date:
        raise CPMValidationError(
            f"Invalid date ordering: planned_finish_date ({finish_date}) cannot be earlier than "
            f"planned_start_date ({start_date})"
        )
    return (finish_date - start_date).days + 1


class CPMService:
    """
    Pure domain service for schedule network graph validation and CPM calculations.
    Stateless, database-agnostic, and deterministic.
    """

    @staticmethod
    def validate_network(
        activities: list[CPMActivityInput],
        dependencies: list[CPMDependencyInput],
        project_id: UUID | None = None,
    ) -> None:
        """
        Validates schedule activities and dependencies:
          1. Activity IDs are unique.
          2. All dependency predecessor_id and successor_id reference known activities.
          3. No self-dependencies (predecessor == successor).
          4. No duplicate directed edges.
          5. All items belong to the same project_id context (if provided).
        """
        activity_map: dict[UUID, CPMActivityInput] = {}
        target_project_id = project_id

        for act in activities:
            if act.activity_id in activity_map:
                raise CPMValidationError(f"Duplicate activity_id in input: {act.activity_id}")
            if target_project_id is None:
                target_project_id = act.project_id
            elif act.project_id != target_project_id:
                raise CPMValidationError(
                    f"Cross-project activity detected: expected project {target_project_id}, got {act.project_id}"
                )
            activity_map[act.activity_id] = act

        seen_edges: set[tuple[UUID, UUID]] = set()
        for dep in dependencies:
            if target_project_id is not None and dep.project_id != target_project_id:
                raise CPMValidationError(
                    f"Cross-project dependency detected: expected project {target_project_id}, got {dep.project_id}"
                )
            if dep.predecessor_id not in activity_map:
                raise CPMValidationError(
                    f"Dependency references unknown predecessor_id: {dep.predecessor_id}"
                )
            if dep.successor_id not in activity_map:
                raise CPMValidationError(
                    f"Dependency references unknown successor_id: {dep.successor_id}"
                )
            if dep.predecessor_id == dep.successor_id:
                raise CPMValidationError(
                    f"Self-dependency detected on activity: {dep.predecessor_id}"
                )
            edge_key = (dep.predecessor_id, dep.successor_id)
            if edge_key in seen_edges:
                raise CPMValidationError(
                    f"Duplicate dependency edge between {dep.predecessor_id} and {dep.successor_id}"
                )
            seen_edges.add(edge_key)

    @staticmethod
    def topological_sort(
        activities: list[CPMActivityInput],
        dependencies: list[CPMDependencyInput],
    ) -> list[CPMActivityInput]:
        """
        Produces a deterministic topological ordering of activities using Kahn's algorithm.
        Ties are broken deterministically using (activity_code ASC, activity_id ASC).
        Raises CPMGraphCycleError if a cycle is detected.
        """
        activity_map = {act.activity_id: act for act in activities}
        in_degree: dict[UUID, int] = {act.activity_id: 0 for act in activities}
        adj_list: dict[UUID, list[CPMDependencyInput]] = defaultdict(list)

        for dep in dependencies:
            adj_list[dep.predecessor_id].append(dep)
            in_degree[dep.successor_id] += 1

        # Priority queue for deterministic tie-breaking: (activity_code, str(activity_id), activity_id)
        heap: list[tuple[str, str, UUID]] = []
        for act_id, deg in in_degree.items():
            if deg == 0:
                act = activity_map[act_id]
                heappush(heap, (act.activity_code, str(act.activity_id), act_id))

        topological_order: list[CPMActivityInput] = []

        while heap:
            _, _, act_id = heappop(heap)
            act = activity_map[act_id]
            topological_order.append(act)

            for dep in adj_list[act_id]:
                succ_id = dep.successor_id
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    succ_act = activity_map[succ_id]
                    heappush(heap, (succ_act.activity_code, str(succ_act.activity_id), succ_id))

        if len(topological_order) < len(activities):
            unresolved = [act.activity_code for act in activities if in_degree[act.activity_id] > 0]
            raise CPMGraphCycleError(
                f"Dependency cycle detected involving activities: {', '.join(unresolved)}"
            )

        return topological_order

    @staticmethod
    def calculate_cpm(
        activities: list[CPMActivityInput],
        dependencies: list[CPMDependencyInput],
        project_id: UUID | None = None,
    ) -> CPMNetworkResult:
        """
        Executes complete Critical Path Method (CPM) analysis:
          1. Network validation and tenant containment.
          2. Topological sort and cycle detection.
          3. Forward pass (Early Start, Early Finish).
          4. Backward pass (Late Start, Late Finish).
          5. Float calculation (Total Float, Free Float).
          6. Critical Path extraction.
        """
        if not activities:
            proj_id = project_id or (dependencies[0].project_id if dependencies else UUID(int=0))
            return CPMNetworkResult(
                project_id=proj_id,
                project_start_date=None,
                project_finish_date=None,
                total_activities=0,
                critical_activities_count=0,
                nodes=[],
                critical_path=[],
            )

        target_project_id = project_id or activities[0].project_id
        CPMService.validate_network(activities, dependencies, target_project_id)

        # 1. Topological ordering
        sorted_activities = CPMService.topological_sort(activities, dependencies)
        activity_map = {act.activity_id: act for act in sorted_activities}

        # 2. Activity durations
        durations: dict[UUID, int] = {
            act.activity_id: calculate_activity_duration(act.planned_start_date, act.planned_finish_date)
            for act in sorted_activities
        }

        # 3. Adjacency mappings
        incoming_deps: dict[UUID, list[CPMDependencyInput]] = defaultdict(list)
        outgoing_deps: dict[UUID, list[CPMDependencyInput]] = defaultdict(list)
        for dep in dependencies:
            incoming_deps[dep.successor_id].append(dep)
            outgoing_deps[dep.predecessor_id].append(dep)

        # 4. Project Start Date Anchor
        valid_start_dates = [
            act.planned_start_date for act in sorted_activities if act.planned_start_date is not None
        ]
        project_start_anchor = min(valid_start_dates) if valid_start_dates else date.today()

        # ======================================================================
        # 5. Forward Pass (Early Dates)
        # ======================================================================
        early_start: dict[UUID, date] = {}
        early_finish: dict[UUID, date] = {}

        for act in sorted_activities:
            act_id = act.activity_id
            dur = durations[act_id]
            inc_edges = incoming_deps[act_id]

            if not inc_edges:
                # Start node: use baseline planned_start_date or project start anchor
                es = act.planned_start_date if act.planned_start_date is not None else project_start_anchor
            else:
                candidate_es_list: list[date] = []
                for dep in inc_edges:
                    pred_id = dep.predecessor_id
                    pred_es = early_start[pred_id]
                    pred_ef = early_finish[pred_id]
                    lag = dep.lag_days
                    rel = dep.relationship_type

                    if rel == DependencyRelationshipType.FS:
                        # ES_j >= EF_i + 1 + lag
                        cand_es = pred_ef + timedelta(days=1 + lag)
                    elif rel == DependencyRelationshipType.SS:
                        # ES_j >= ES_i + lag
                        cand_es = pred_es + timedelta(days=lag)
                    elif rel == DependencyRelationshipType.FF:
                        # EF_j >= EF_i + lag => ES_j >= EF_i + lag - dur + 1
                        cand_es = pred_ef + timedelta(days=lag - max(1, dur) + 1)
                    elif rel == DependencyRelationshipType.SF:
                        # EF_j >= ES_i + lag => ES_j >= ES_i + lag - dur + 1
                        cand_es = pred_es + timedelta(days=lag - max(1, dur) + 1)
                    else:
                        raise CPMValidationError(f"Unsupported relationship type: {rel}")

                    candidate_es_list.append(cand_es)

                # If activity has explicit planned_start_date that is later than all predecessors, respect baseline anchor
                if act.planned_start_date is not None:
                    candidate_es_list.append(act.planned_start_date)

                es = max(candidate_es_list)

            early_start[act_id] = es
            ef = es + timedelta(days=dur - 1) if dur > 0 else es
            early_finish[act_id] = ef

        # ======================================================================
        # 6. Backward Pass (Late Dates)
        # ======================================================================
        terminal_nodes = [act for act in sorted_activities if not outgoing_deps[act.activity_id]]
        if not terminal_nodes:
            terminal_nodes = sorted_activities

        project_finish_anchor = max((early_finish[t.activity_id] for t in terminal_nodes), default=project_start_anchor)

        late_start: dict[UUID, date] = {}
        late_finish: dict[UUID, date] = {}

        for act in reversed(sorted_activities):
            act_id = act.activity_id
            dur = durations[act_id]
            out_edges = outgoing_deps[act_id]

            if not out_edges:
                # Terminal node: late finish equals project finish anchor
                lf = project_finish_anchor
            else:
                candidate_lf_list: list[date] = []
                for dep in out_edges:
                    succ_id = dep.successor_id
                    succ_ls = late_start[succ_id]
                    succ_lf = late_finish[succ_id]
                    lag = dep.lag_days
                    rel = dep.relationship_type

                    if rel == DependencyRelationshipType.FS:
                        # LF_i <= LS_j - 1 - lag
                        cand_lf = succ_ls - timedelta(days=1 + lag)
                    elif rel == DependencyRelationshipType.SS:
                        # LS_i <= LS_j - lag => LF_i <= LS_j - lag + dur - 1
                        cand_lf = succ_ls - timedelta(days=lag - max(1, dur) + 1)
                    elif rel == DependencyRelationshipType.FF:
                        # LF_i <= LF_j - lag
                        cand_lf = succ_lf - timedelta(days=lag)
                    elif rel == DependencyRelationshipType.SF:
                        # LS_i <= LF_j - lag => LF_i <= LF_j - lag + dur - 1
                        cand_lf = succ_lf - timedelta(days=lag - max(1, dur) + 1)
                    else:
                        raise CPMValidationError(f"Unsupported relationship type: {rel}")

                    candidate_lf_list.append(cand_lf)

                lf = min(candidate_lf_list)

            late_finish[act_id] = lf
            ls = lf - timedelta(days=dur - 1) if dur > 0 else lf
            late_start[act_id] = ls

        # ======================================================================
        # 7. Float Calculations & Critical Path Extraction
        # ======================================================================
        total_float: dict[UUID, int] = {}
        free_float: dict[UUID, int] = {}
        nodes: list[CPMActivityNode] = []
        critical_path_ids: list[UUID] = []

        for act in sorted_activities:
            act_id = act.activity_id
            es = early_start[act_id]
            ef = early_finish[act_id]
            ls = late_start[act_id]
            lf = late_finish[act_id]
            dur = durations[act_id]

            tf = (ls - es).days
            total_float[act_id] = tf

            out_edges = outgoing_deps[act_id]
            if not out_edges:
                ff = tf
            else:
                candidate_ff_limits: list[int] = []
                for dep in out_edges:
                    succ_id = dep.successor_id
                    succ_es = early_start[succ_id]
                    succ_ef = early_finish[succ_id]
                    lag = dep.lag_days
                    rel = dep.relationship_type

                    if rel == DependencyRelationshipType.FS:
                        allowed_ef = succ_es - timedelta(days=1 + lag)
                    elif rel == DependencyRelationshipType.SS:
                        # allowed_ES = succ_es - lag => allowed_EF = succ_es - lag + dur - 1
                        allowed_ef = succ_es - timedelta(days=lag - max(1, dur) + 1)
                    elif rel == DependencyRelationshipType.FF:
                        allowed_ef = succ_ef - timedelta(days=lag)
                    elif rel == DependencyRelationshipType.SF:
                        allowed_ef = succ_ef - timedelta(days=lag - max(1, dur) + 1)
                    else:
                        raise CPMValidationError(f"Unsupported relationship type: {rel}")

                    candidate_ff_limits.append((allowed_ef - ef).days)

                ff = max(0, min(candidate_ff_limits)) if candidate_ff_limits else tf

            free_float[act_id] = ff
            is_crit = tf <= 0

            if is_crit:
                critical_path_ids.append(act_id)

            nodes.append(
                CPMActivityNode(
                    activity_id=act.activity_id,
                    project_id=act.project_id,
                    activity_code=act.activity_code,
                    name=act.name,
                    wbs_code=act.wbs_code,
                    discipline=act.discipline,
                    location=act.location,
                    planned_start_date=act.planned_start_date,
                    planned_finish_date=act.planned_finish_date,
                    duration_days=dur,
                    early_start=es,
                    early_finish=ef,
                    late_start=ls,
                    late_finish=lf,
                    total_float=tf,
                    free_float=ff,
                    is_critical=is_crit,
                )
            )

        return CPMNetworkResult(
            project_id=target_project_id,
            project_start_date=project_start_anchor,
            project_finish_date=project_finish_anchor,
            total_activities=len(nodes),
            critical_activities_count=len(critical_path_ids),
            nodes=nodes,
            critical_path=critical_path_ids,
        )


cpm_service = CPMService()
