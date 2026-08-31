"""
SiteSync AI — Phase 9.2 Critical Path Method (CPM) Pure Domain Engine Math Tests.
Comprehensive deterministic tests covering:
  - TEST 1: Duration calculation (inclusive calendar days)
  - TEST 2: Linear FS network (ADR-015 Example 1)
  - TEST 3: Branching network with mixed FS/SS/FF relationships (ADR-015 Example 2)
  - TEST 4: SS relationship with lag
  - TEST 5: FF relationship
  - TEST 6: SF relationship
  - TEST 7: Positive lag
  - TEST 8: Negative lag (lead)
  - TEST 9: Multiple predecessors convergence (max constraint)
  - TEST 10: Multiple successors burst (min constraint)
  - TEST 11: Multi-node cycle detection
  - TEST 12: Two-node cycle detection
  - TEST 13: Unknown activity reference validation
  - TEST 14: Duplicate edge rejection
  - TEST 15: Self-dependency rejection
  - TEST 16: Invalid relationship type rejection
  - TEST 17: Missing dates handling
  - TEST 18: Invalid date range rejection
  - TEST 19: Deterministic topological ordering
  - TEST 20: Multiple parallel critical branches
  - TEST 21: Static boundary scan for Phase 9.3+ identifiers
"""

from __future__ import annotations

import inspect
from datetime import date
from uuid import UUID, uuid4
import pytest

import app.schemas.cpm as cpm_schemas
import app.services.cpm_service as cpm_service_mod
from app.schemas.cpm import (
    CPMActivityInput,
    CPMDependencyInput,
    DependencyRelationshipType,
)
from app.services.cpm_service import (
    CPMGraphCycleError,
    CPMService,
    CPMValidationError,
    calculate_activity_duration,
    cpm_service,
)

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
# TEST 1 — Duration Calculation
# ==============================================================================

def test_1_duration_calculation_inclusive_calendar_days():
    """
    Verifies D_i = (finish - start) + 1 calendar days:
      - 2026-01-01 to 2026-01-10 -> 10 days
      - 2026-01-01 to 2026-01-01 -> 1 day
      - Missing dates -> 0 days
    """
    assert calculate_activity_duration(date(2026, 1, 1), date(2026, 1, 10)) == 10
    assert calculate_activity_duration(date(2026, 1, 1), date(2026, 1, 1)) == 1
    assert calculate_activity_duration(None, date(2026, 1, 10)) == 0
    assert calculate_activity_duration(date(2026, 1, 1), None) == 0
    assert calculate_activity_duration(None, None) == 0


# ==============================================================================
# TEST 2 — Linear FS Network (ADR-015 Example 1)
# ==============================================================================

def test_2_linear_fs_network():
    """
    A (10d, 2026-01-01 to 2026-01-10) -> B (5d, 2026-01-11 to 2026-01-15) -> C (5d, 2026-01-16 to 2026-01-20)
    All on critical path (TF = 0).
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 15), act_id=id_b),
        make_act("C", date(2026, 1, 16), date(2026, 1, 20), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=0),
        make_dep(id_b, id_c, DependencyRelationshipType.FS, lag=0),
    ]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert res.total_activities == 3
    assert res.critical_activities_count == 3
    assert res.critical_path == [id_a, id_b, id_c]

    # Node A
    assert node_map["A"].early_start == date(2026, 1, 1)
    assert node_map["A"].early_finish == date(2026, 1, 10)
    assert node_map["A"].late_start == date(2026, 1, 1)
    assert node_map["A"].late_finish == date(2026, 1, 10)
    assert node_map["A"].total_float == 0
    assert node_map["A"].free_float == 0
    assert node_map["A"].is_critical is True

    # Node B
    assert node_map["B"].early_start == date(2026, 1, 11)
    assert node_map["B"].early_finish == date(2026, 1, 15)
    assert node_map["B"].late_start == date(2026, 1, 11)
    assert node_map["B"].late_finish == date(2026, 1, 15)
    assert node_map["B"].total_float == 0
    assert node_map["B"].free_float == 0
    assert node_map["B"].is_critical is True

    # Node C
    assert node_map["C"].early_start == date(2026, 1, 16)
    assert node_map["C"].early_finish == date(2026, 1, 20)
    assert node_map["C"].late_start == date(2026, 1, 16)
    assert node_map["C"].late_finish == date(2026, 1, 20)
    assert node_map["C"].total_float == 0
    assert node_map["C"].free_float == 0
    assert node_map["C"].is_critical is True


# ==============================================================================
# TEST 3 — Branching / Float Network (ADR-015 Example 2)
# ==============================================================================

def test_3_branching_mixed_relationship_network():
    """
    A (10d, 1-10)
    B (10d, 11-20, FS from A)
    C (4d, 11-14, SS from A with lag 2)
    D (5d, 21-25, FS from B, FF from C)
    """
    id_a, id_b, id_c, id_d = uuid4(), uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 11), date(2026, 1, 20), act_id=id_b),
        make_act("C", date(2026, 1, 11), date(2026, 1, 14), act_id=id_c),
        make_act("D", date(2026, 1, 21), date(2026, 1, 25), act_id=id_d),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=0),
        make_dep(id_a, id_c, DependencyRelationshipType.SS, lag=2),
        make_dep(id_b, id_d, DependencyRelationshipType.FS, lag=0),
        make_dep(id_c, id_d, DependencyRelationshipType.FF, lag=0),
    ]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    # Critical path is A -> B -> D
    assert node_map["A"].is_critical is True
    assert node_map["B"].is_critical is True
    assert node_map["D"].is_critical is True
    assert node_map["C"].is_critical is False

    # Activity C has positive total float
    assert node_map["C"].total_float == 11
    assert node_map["C"].is_critical is False


# ==============================================================================
# TEST 4 — SS Relationship
# ==============================================================================

def test_4_start_to_start_relationship():
    """
    A duration 10 (Day 1-10)
    B duration 5
    A -> B SS lag 2 => ES_B = ES_A + 2 = Day 3
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", None, None, act_id=id_b),
    ]
    # Set explicit dates on B to test 5-day duration
    acts[1].planned_start_date = date(2026, 1, 3)
    acts[1].planned_finish_date = date(2026, 1, 7)

    deps = [make_dep(id_a, id_b, DependencyRelationshipType.SS, lag=2)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_start == date(2026, 1, 3)
    assert node_map["B"].early_finish == date(2026, 1, 7)


# ==============================================================================
# TEST 5 — FF Relationship
# ==============================================================================

def test_5_finish_to_finish_relationship():
    """
    A duration 10 (Day 1-10)
    B duration 5
    A -> B FF lag 0 => EF_B >= EF_A = Day 10 => ES_B = 10 - 5 + 1 = Day 6
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 1), date(2026, 1, 5), act_id=id_b),  # 5d duration
    ]
    deps = [make_dep(id_a, id_b, DependencyRelationshipType.FF, lag=0)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_finish == date(2026, 1, 10)
    assert node_map["B"].early_start == date(2026, 1, 6)


# ==============================================================================
# TEST 6 — SF Relationship
# ==============================================================================

def test_6_start_to_finish_relationship():
    """
    A duration 10 (Day 1-10)
    B duration 5 (Day 1-5)
    A -> B SF lag 0 => EF_B >= ES_A = Day 1 => ES_B = 1 - 5 + 1 = Day -3 relative to anchor
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 5), date(2026, 1, 14), act_id=id_a),
        make_act("B", date(2026, 1, 1), date(2026, 1, 5), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b, DependencyRelationshipType.SF, lag=0)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_finish >= node_map["A"].early_start


# ==============================================================================
# TEST 7 — Positive Lag
# ==============================================================================

def test_7_positive_lag_finish_to_start():
    """
    A duration 10 (Day 1-10).
    A -> B FS lag +3 => ES_B = EF_A + 1 + 3 = Day 14.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 14), date(2026, 1, 18), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=3)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_start == date(2026, 1, 14)


# ==============================================================================
# TEST 8 — Negative Lag / Lead
# ==============================================================================

def test_8_negative_lag_lead_finish_to_start():
    """
    A duration 10 (Day 1-10).
    A -> B FS lag -2 (2 days lead) => ES_B = EF_A + 1 - 2 = Day 9.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 9), date(2026, 1, 13), act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=-2)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_start == date(2026, 1, 9)


# ==============================================================================
# TEST 9 — Multiple Predecessors Convergence
# ==============================================================================

def test_9_multiple_predecessors_takes_max_constraint():
    """
    A finishes Day 10 (ES_B candidate = Day 11)
    C finishes Day 15 (ES_B candidate = Day 16)
    B must start at max(11, 16) = Day 16.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("C", date(2026, 1, 1), date(2026, 1, 15), act_id=id_c),
        make_act("B", date(2026, 1, 16), date(2026, 1, 20), act_id=id_b),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=0),
        make_dep(id_c, id_b, DependencyRelationshipType.FS, lag=0),
    ]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B"].early_start == date(2026, 1, 16)


# ==============================================================================
# TEST 10 — Multiple Successors Burst
# ==============================================================================

def test_10_multiple_successors_takes_min_late_finish_constraint():
    """
    A (Day 1-10).
    A -> B (LS_B = Day 15 => LF_A candidate = Day 14).
    A -> C (LS_C = Day 12 => LF_A candidate = Day 11).
    LF_A must be min(14, 11) = Day 11.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 10), act_id=id_a),
        make_act("B", date(2026, 1, 15), date(2026, 1, 20), act_id=id_b),
        make_act("C", date(2026, 1, 12), date(2026, 1, 20), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS, lag=0),
        make_dep(id_a, id_c, DependencyRelationshipType.FS, lag=0),
    ]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["A"].late_finish == date(2026, 1, 11)


# ==============================================================================
# TEST 11 — Multi-Node Cycle Detection
# ==============================================================================

def test_11_three_node_cycle_detected():
    """
    A -> B -> C -> A cycle raises CPMGraphCycleError.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
        make_act("C", date(2026, 1, 11), date(2026, 1, 15), act_id=id_c),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS),
        make_dep(id_b, id_c, DependencyRelationshipType.FS),
        make_dep(id_c, id_a, DependencyRelationshipType.FS),
    ]

    with pytest.raises(CPMGraphCycleError) as exc_info:
        cpm_service.calculate_cpm(acts, deps)
    assert "Dependency cycle detected" in str(exc_info.value)


# ==============================================================================
# TEST 12 — Two-Node Cycle Detection
# ==============================================================================

def test_12_two_node_cycle_detected():
    """
    A -> B -> A cycle raises CPMGraphCycleError.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS),
        make_dep(id_b, id_a, DependencyRelationshipType.FS),
    ]

    with pytest.raises(CPMGraphCycleError):
        cpm_service.calculate_cpm(acts, deps)


# ==============================================================================
# TEST 13 — Unknown Activity Reference
# ==============================================================================

def test_13_unknown_activity_in_dependency():
    """
    Dependency referencing non-existent predecessor raises CPMValidationError.
    """
    id_a = uuid4()
    acts = [make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a)]
    deps = [make_dep(uuid4(), id_a)]

    with pytest.raises(CPMValidationError) as exc_info:
        cpm_service.calculate_cpm(acts, deps)
    assert "unknown predecessor_id" in str(exc_info.value)


# ==============================================================================
# TEST 14 — Duplicate Edge Rejection
# ==============================================================================

def test_14_duplicate_dependency_edge():
    """
    Two dependency edges between same (predecessor, successor) raise CPMValidationError.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS),
        make_dep(id_a, id_b, DependencyRelationshipType.SS),
    ]

    with pytest.raises(CPMValidationError) as exc_info:
        cpm_service.calculate_cpm(acts, deps)
    assert "Duplicate dependency edge" in str(exc_info.value)


# ==============================================================================
# TEST 15 — Self Dependency Rejection
# ==============================================================================

def test_15_self_dependency_validation_error():
    """
    Predecessor == Successor raises error.
    """
    id_a = uuid4()
    with pytest.raises(Exception):
        make_dep(id_a, id_a)


# ==============================================================================
# TEST 16 — Invalid Relationship Type
# ==============================================================================

def test_16_invalid_relationship_type():
    """
    Invalid relationship type rejected by validation.
    """
    with pytest.raises(Exception):
        CPMDependencyInput(
            dependency_id=uuid4(),
            project_id=PROJECT_ID,
            predecessor_id=uuid4(),
            successor_id=uuid4(),
            relationship_type="INVALID",  # type: ignore
        )


# ==============================================================================
# TEST 17 — Missing Dates Handling
# ==============================================================================

def test_17_missing_dates_handling_zero_duration():
    """
    Milestone activity with None dates has duration 0 and falls back to project anchor.
    """
    id_a, id_b = uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B_MILESTONE", None, None, act_id=id_b),
    ]
    deps = [make_dep(id_a, id_b, DependencyRelationshipType.FS)]

    res = cpm_service.calculate_cpm(acts, deps)
    node_map = {n.activity_code: n for n in res.nodes}

    assert node_map["B_MILESTONE"].duration_days == 0
    assert node_map["B_MILESTONE"].early_start == date(2026, 1, 6)
    assert node_map["B_MILESTONE"].early_finish == date(2026, 1, 6)


# ==============================================================================
# TEST 18 — Invalid Date Range
# ==============================================================================

def test_18_invalid_date_range_rejected():
    """
    planned_finish_date < planned_start_date raises ValidationError.
    """
    with pytest.raises(Exception):
        make_act("A", date(2026, 1, 10), date(2026, 1, 5))


# ==============================================================================
# TEST 19 — Deterministic Topological Ordering
# ==============================================================================

def test_19_deterministic_topological_ordering():
    """
    Verifies that running CPM analysis multiple times on parallel nodes produces identical order.
    """
    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    acts = [
        make_act("C", date(2026, 1, 1), date(2026, 1, 5), act_id=id_c),
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 1), date(2026, 1, 5), act_id=id_b),
    ]

    res1 = cpm_service.calculate_cpm(acts, [])
    res2 = cpm_service.calculate_cpm(acts, [])

    codes1 = [n.activity_code for n in res1.nodes]
    codes2 = [n.activity_code for n in res2.nodes]

    assert codes1 == ["A", "B", "C"]
    assert codes2 == ["A", "B", "C"]


# ==============================================================================
# TEST 20 — Multiple Parallel Critical Branches
# ==============================================================================

def test_20_multiple_parallel_critical_branches():
    """
    Two independent parallel paths of equal total duration (10 days):
      Path 1: A (5d) -> B (5d) = 10d
      Path 2: C (5d) -> D (5d) = 10d
    All 4 activities have TF = 0 and must be retained in critical path.
    """
    id_a, id_b, id_c, id_d = uuid4(), uuid4(), uuid4(), uuid4()
    acts = [
        make_act("A", date(2026, 1, 1), date(2026, 1, 5), act_id=id_a),
        make_act("B", date(2026, 1, 6), date(2026, 1, 10), act_id=id_b),
        make_act("C", date(2026, 1, 1), date(2026, 1, 5), act_id=id_c),
        make_act("D", date(2026, 1, 6), date(2026, 1, 10), act_id=id_d),
    ]
    deps = [
        make_dep(id_a, id_b, DependencyRelationshipType.FS),
        make_dep(id_c, id_d, DependencyRelationshipType.FS),
    ]

    res = cpm_service.calculate_cpm(acts, deps)

    assert res.total_activities == 4
    assert res.critical_activities_count == 4
    assert set(res.critical_path) == {id_a, id_b, id_c, id_d}


# ==============================================================================
# TEST 21 — Static Phase Boundary Check
# ==============================================================================

def test_21_static_phase_boundary_check():
    """
    Scans Phase 9.2 source modules and confirms ZERO occurrence of forbidden Phase 9.3+ identifiers.
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
        "forecast",
        "downstream_impact",
        "cost_variance",
        "cpi",
        "spi",
    ]

    modules = [cpm_schemas, cpm_service_mod]

    for mod in modules:
        src = inspect.getsource(mod).lower()
        for token in forbidden_tokens:
            assert token not in src, f"Forbidden later-phase token '{token}' found in {mod.__name__}"
