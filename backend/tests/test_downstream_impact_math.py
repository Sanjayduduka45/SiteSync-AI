"""
SiteSync AI — Phase 9.3 Downstream Impact & Float Erosion Math Tests.
Comprehensive deterministic unit tests covering:
  - TEST 1: Linear A -> B -> C traversal
  - TEST 2: Branching A -> B and A -> C traversal
  - TEST 3: Converging A -> B -> D and A -> C -> D (deduplicated)
  - TEST 4: Delay within available float -> BUFFER_ABSORBED
  - TEST 5: Delay exceeding available float -> CRITICAL_SLIPPAGE
  - TEST 6: Completed downstream activity -> HISTORICAL_COMPLETED
  - TEST 7: Activity with no successors returns empty downstream impact
  - TEST 8: Cyclic graph rejected at CPM calculation boundary
  - TEST 9: PDM relationship metadata preserved (FS, SS, FF, SF, lag)
  - TEST 10: Cross-project dependency containment rejected
  - TEST 11: Deterministic traversal ordering
  - TEST 12: Missing dates / zero duration milestones
  - TEST 13: Non-positive delay (0 or negative) -> UNAFFECTED
  - TEST 14: Deep multi-tier network traversal
  - TEST 15: Static Phase Boundary check for Phase 9.4+ identifiers
"""

from __future__ import annotations

import inspect
from datetime import date
from uuid import UUID, uuid4
import pytest

import app.schemas.downstream_impact as downstream_schemas
import app.services.downstream_impact_service as downstream_service_mod
from app.schemas.cpm import (
    CPMActivityInput,
    CPMDependencyInput,
    DependencyRelationshipType,
)
from app.schemas.downstream_impact import DownstreamImpactSeverity
from app.services.cpm_service import CPMValidationError, cpm_service
from app.services.downstream_impact_service import downstream_impact_service

PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_act(
    code: str,
    start: date | None = None,
    finish: date | None = None,
    act_id: UUID | None = None,
    name: str | None = None,
    wbs: str | None = None,
) -> CPMActivityInput:
    return CPMActivityInput(
        activity_id=act_id or uuid4(),
        project_id=PROJECT_ID,
        activity_code=code,
        name=name or f"Activity {code}",
        wbs_code=wbs,
        planned_start_date=start,
        planned_finish_date=finish,
    )


def make_dep(
    pred_id: UUID,
    succ_id: UUID,
    rel: DependencyRelationshipType = DependencyRelationshipType.FS,
    lag: int = 0,
) -> CPMDependencyInput:
    return CPMDependencyInput(
        dependency_id=uuid4(),
        project_id=PROJECT_ID,
        predecessor_id=pred_id,
        successor_id=succ_id,
        relationship_type=rel,
        lag_days=lag,
    )


# ==============================================================================
# TEST 1 — Linear A -> B -> C Traversal
# ==============================================================================

def test_1_linear_downstream_traversal():
    """
    A -> B -> C.
    Delaying A by 3 days:
    Both B and C are reachable at depth 1 and depth 2.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),
        make_act("C", date(2026, 1, 16), date(2026, 1, 20), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_b),
        make_dep(id_b, id_c),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, deps)
    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=3,
    )

    assert impact.total_downstream_activities_count == 2
    codes = [s.activity_code for s in impact.impacted_successors]
    assert codes == ["B", "C"]
    assert impact.impacted_successors[0].depth == 1
    assert impact.impacted_successors[0].path == ["A", "B"]
    assert impact.impacted_successors[1].depth == 2
    assert impact.impacted_successors[1].path == ["A", "B", "C"]


# ==============================================================================
# TEST 2 — Branching A -> B and A -> C
# ==============================================================================

def test_2_branching_downstream_traversal():
    """
    A -> B and A -> C (fan-out).
    Both B and C are reachable at depth 1.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),
        make_act("C", date(2026, 1, 11), date(2026, 1, 15), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_b),
        make_dep(id_a, id_c),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, deps)
    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=2,
    )

    assert impact.total_downstream_activities_count == 2
    assert {s.activity_code for s in impact.impacted_successors} == {"B", "C"}
    for s in impact.impacted_successors:
        assert s.depth == 1


# ==============================================================================
# TEST 3 — Converging A -> B -> D and A -> C -> D (Deduplication)
# ==============================================================================

def test_3_converging_diamond_network_deduplication():
    """
    A -> B -> D and A -> C -> D.
    Activity D is reachable via two separate paths, but must be returned exactly once.
    """
    id_a, id_b, id_c, id_d = uuid4(), uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
        make_act("C", date(2026, 1, 6), date(2026, 1, 10), act_id=id_c),
        make_act("D", date(2026, 1, 11), date(2026, 1, 15), act_id=id_d),
    ]
    deps = [
        make_dep(id_a, id_b),
        make_dep(id_a, id_c),
        make_dep(id_b, id_d),
        make_dep(id_c, id_d),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, deps)
    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=2,
    )

    assert impact.total_downstream_activities_count == 3
    codes = [s.activity_code for s in impact.impacted_successors]
    assert codes == ["B", "C", "D"]
    # D occurs exactly once
    assert codes.count("D") == 1
    d_node = next(s for s in impact.impacted_successors if s.activity_code == "D")
    assert d_node.depth == 2


# ==============================================================================
# TEST 4 — Delay Absorbed by Available Float
# ==============================================================================

def test_4_delay_absorbed_by_available_float():
    """
    Activity A (10d, 1-10) -> Activity B (5d, float = 10d).
    Delay of 4 days on A:
    4 <= 10 -> BUFFER_ABSORBED, float_consumed = 4, projected_delay_days = 0.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),  # Has float because of longer parallel branch C
        make_act("C", date(2026, 1, 1), date(2026, 1, 25), act_id=id_c),   # Critical path (25 days)
    ]
    deps = [
        make_dep(id_a, id_b),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, deps)
    # B has 10 days total float (Project finish is Day 25, B finishes Day 15)
    b_cpm = next(n for n in cpm_res.nodes if n.activity_code == "B")
    assert b_cpm.total_float == 10

    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=4,
    )

    b_impact = impact.impacted_successors[0]
    assert b_impact.impact_severity == DownstreamImpactSeverity.BUFFER_ABSORBED
    assert b_impact.float_consumed == 4
    assert b_impact.projected_delay_days == 0
    assert impact.buffer_absorbed_count == 1
    assert impact.critical_slippage_count == 0


# ==============================================================================
# TEST 5 — Delay Exceeding Available Float (Critical Slippage)
# ==============================================================================

def test_5_delay_exceeding_float_causes_critical_slippage():
    """
    Activity A -> Activity B (float = 3d).
    Delay of 7 days on A:
    7 > 3 -> CRITICAL_SLIPPAGE, float_consumed = 3, projected_delay_days = 4.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),
        make_act("C", date(2026, 1, 1), date(2026, 1, 18), act_id=id_c),  # Project finish is Day 18 -> B has TF = 3
    ]
    deps = [make_dep(id_a, id_b)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=7,
    )

    b_impact = impact.impacted_successors[0]
    assert b_impact.impact_severity == DownstreamImpactSeverity.CRITICAL_SLIPPAGE
    assert b_impact.float_consumed == 3
    assert b_impact.projected_delay_days == 4
    assert impact.critical_slippage_count == 1
    assert impact.buffer_absorbed_count == 0


# ==============================================================================
# TEST 6 — Completed Downstream Activity Historical Exclusion
# ==============================================================================

def test_6_completed_activity_historical_exclusion():
    """
    A -> B -> C.
    B is already verified COMPLETED.
    B is classified as HISTORICAL_COMPLETED, float_consumed = 0, projected_delay = 0.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
        make_act("C", date(2026, 1, 11), date(2026, 1, 15), act_id=id_c),
    ]
    deps = [make_dep(id_a, id_b), make_dep(id_b, id_c)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=5,
        completed_activity_ids={id_b},
    )

    b_impact = next(s for s in impact.impacted_successors if s.activity_code == "B")
    assert b_impact.impact_severity == DownstreamImpactSeverity.HISTORICAL_COMPLETED
    assert b_impact.is_completed is True
    assert b_impact.float_consumed == 0
    assert b_impact.projected_delay_days == 0
    assert impact.historical_completed_count == 1


# ==============================================================================
# TEST 7 — Activity with No Successors Returns Empty List
# ==============================================================================

def test_7_terminal_activity_no_successors():
    """
    Activity with out-degree 0 returns total_downstream_activities_count = 0.
    """
    id_a = uuid4()
    acts = [make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a)]
    cpm_res = cpm_service.calculate_cpm(acts, [])

    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=[],
        source_activity_id=id_a,
        factual_delay_days=3,
    )
    assert impact.total_downstream_activities_count == 0
    assert impact.impacted_successors == []


# ==============================================================================
# TEST 8 — Cyclic Graph Validation
# ==============================================================================

def test_8_cyclic_graph_rejected_at_cpm_boundary():
    """
    Cyclic graph cannot generate valid CPM input for downstream impact.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b), make_dep(id_b, id_a)]

    with pytest.raises(Exception):
        cpm_service.calculate_cpm(acts, deps)


# ==============================================================================
# TEST 9 — PDM Relationship Metadata Preserved
# ==============================================================================

def test_9_pdm_relationship_metadata_preserved():
    """
    A -> B (SS with lag 2).
    Downstream impact node on B preserves relationship_with_immediate_predecessor and lag.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 3), date(2026, 1, 8), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b, rel=DependencyRelationshipType.SS, lag=2)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact = downstream_impact_service.calculate_downstream_impact(
        cpm_result=cpm_res,
        dependencies=deps,
        source_activity_id=id_a,
        factual_delay_days=3,
    )
    b_impact = impact.impacted_successors[0]
    assert b_impact.relationship_with_immediate_predecessor == DependencyRelationshipType.SS
    assert b_impact.lag_days_with_immediate_predecessor == 2


# ==============================================================================
# TEST 10 — Cross-Project Containment Rejected
# ==============================================================================

def test_10_cross_project_dependency_rejected():
    """
    Dependency belonging to another project raises CPMValidationError.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, [make_dep(id_a, id_b)])

    # Craft dependency with different project_id
    foreign_dep = CPMDependencyInput(
        dependency_id=uuid4(),
        project_id=uuid4(),  # Different project
        predecessor_id=id_a,
        successor_id=id_b,
        relationship_type=DependencyRelationshipType.FS,
        lag_days=0,
    )

    with pytest.raises(CPMValidationError) as exc_info:
        downstream_impact_service.calculate_downstream_impact(
            cpm_result=cpm_res,
            dependencies=[foreign_dep],
            source_activity_id=id_a,
            factual_delay_days=3,
        )
    assert "Cross-project dependency detected" in str(exc_info.value)


# ==============================================================================
# TEST 11 — Deterministic Traversal Ordering
# ==============================================================================

def test_11_deterministic_traversal_ordering():
    """
    Multiple parallel successors are sorted by (depth ASC, activity_code ASC, activity_id ASC).
    """
    id_a, id_b, id_c, id_d = uuid4(), uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("D", date(2026, 1, 6), date(2026, 1, 10), act_id=id_d),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
        make_act("C", date(2026, 1, 6), date(2026, 1, 10), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_d),
        make_dep(id_a, id_b),
        make_dep(id_a, id_c),
    ]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact1 = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, id_a, 2)
    impact2 = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, id_a, 2)

    codes1 = [s.activity_code for s in impact1.impacted_successors]
    codes2 = [s.activity_code for s in impact2.impacted_successors]

    assert codes1 == ["B", "C", "D"]
    assert codes2 == ["B", "C", "D"]


# ==============================================================================
# TEST 12 — Missing Dates / Zero-Duration Milestones
# ==============================================================================

def test_12_milestone_downstream_impact():
    """
    Milestone activity with 0 duration in path.
    """
    id_a, id_m, id_b = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("M_MILESTONE", None, None, act_id=id_m),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_m), make_dep(id_m, id_b)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, id_a, 2)
    assert impact.total_downstream_activities_count == 2
    codes = [s.activity_code for s in impact.impacted_successors]
    assert codes == ["M_MILESTONE", "B"]


# ==============================================================================
# TEST 13 — Zero or Negative Delay (Unaffected)
# ==============================================================================

def test_13_zero_or_negative_delay_unaffected():
    """
    When factual_delay_days <= 0 (on time or early), all downstream successors are UNAFFECTED.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact_zero = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, id_a, 0)
    assert impact_zero.impacted_successors[0].impact_severity == DownstreamImpactSeverity.UNAFFECTED

    impact_neg = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, id_a, -3)
    assert impact_neg.impacted_successors[0].impact_severity == DownstreamImpactSeverity.UNAFFECTED


# ==============================================================================
# TEST 14 — Deep Multi-Tier Network Traversal
# ==============================================================================

def test_14_deep_multi_tier_network():
    """
    A -> B -> C -> D -> E (5-tier chain).
    Source delay = 4 days on critical path (all TF = 0).
    All 4 downstream nodes suffer CRITICAL_SLIPPAGE with projected_delay = 4.
    """
    ids = [uuid4() for _ in range(5)]
    acts = [
        make_act(f"ACT-{i+1}", date(2026, 1, 1 + i*5), date(2026, 1, 5 + i*5), act_id=ids[i])
        for i in range(5)
    ]
    deps = [make_dep(ids[i], ids[i+1]) for i in range(4)]
    cpm_res = cpm_service.calculate_cpm(acts, deps)

    impact = downstream_impact_service.calculate_downstream_impact(cpm_res, deps, ids[0], 4)
    assert impact.total_downstream_activities_count == 4
    assert impact.critical_slippage_count == 4
    for s in impact.impacted_successors:
        assert s.impact_severity == DownstreamImpactSeverity.CRITICAL_SLIPPAGE
        assert s.projected_delay_days == 4


# ==============================================================================
# TEST 15 — Static Phase Boundary Check
# ==============================================================================

def test_15_static_phase_boundary_check():
    """
    Scans Phase 9.3 source modules and confirms ZERO occurrence of forbidden Phase 9.4+ identifiers.
    """
    forbidden_tokens = [
        "risk_score",
        "risk_level",
        "risk_heatmap",
        "critical_path_delay",
        "float_erosion",
        "downstream_bottleneck",
        "predecessor_blocker",
        "delay_prediction",
        "cost_variance",
        "cpi",
        "spi",
    ]

    modules = [downstream_schemas, downstream_service_mod]

    for mod in modules:
        src = inspect.getsource(mod).lower()
        for token in forbidden_tokens:
            assert token not in src, f"Forbidden Phase 9.4+ token '{token}' found in {mod.__name__}"
