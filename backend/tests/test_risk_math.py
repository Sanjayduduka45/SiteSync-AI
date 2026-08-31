"""
SiteSync AI — Phase 9.4 Risk Intelligence & Severity Math Tests.
Comprehensive deterministic unit tests covering:
  - TEST 1: Critical-path delay -> CRITICAL_PATH_DELAY
  - TEST 2: Near-critical delayed activity -> FLOAT_EROSION
  - TEST 3: >=3 direct successors -> DOWNSTREAM_BOTTLENECK
  - TEST 4: >=5 transitive successors -> DOWNSTREAM_BOTTLENECK
  - TEST 5: Predecessor blocked -> PREDECESSOR_BLOCKER
  - TEST 6: Past-due unquantified milestone -> UNQUANTIFIED_MILESTONE_LAG
  - TEST 7: Unit mismatch on critical activity -> UNIT_MISMATCH_EXPOSURE
  - TEST 8: Unit mismatch on safe activity does NOT create UNIT_MISMATCH_EXPOSURE
  - TEST 9: Overlapping categories coexist
  - TEST 10: Critical severity precedence over high/medium/low
  - TEST 11: High severity through near-critical delay
  - TEST 12: High severity through >=5 impacted transitive successors
  - TEST 13: Medium severity through 3<TF<=7 progress lag
  - TEST 14: Medium predecessor-blocker case
  - TEST 15: Low severity for TF>7 with no meaningful variance
  - TEST 16: Score lower bound = 0
  - TEST 17: Score upper bound = 100
  - TEST 18: Critical activity contributes 40 points
  - TEST 19: Float score calculation
  - TEST 20: Fanout score calculation
  - TEST 21: Delay score calculation according to ADR-017
  - TEST 22: Final score rounding
  - TEST 23: Completed activity handling
  - TEST 24: Non-positive delay does not create delay risk
  - TEST 25: Deterministic ordering
  - TEST 26: Extra fields rejected
  - TEST 27: Invalid enum/category rejected
  - TEST 28: No Phase 9.5/API identifiers in domain service
  - TEST 29: No forecasting/ML identifiers or logic
  - TEST 30: Phase boundary static test
"""

from __future__ import annotations

import inspect
from datetime import date
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError

import app.schemas.risk as risk_schemas
import app.services.risk_service as risk_service_mod
from app.schemas.cpm import (
    CPMActivityNode,
    CPMNetworkResult,
)
from app.schemas.downstream_impact import (
    DownstreamImpactResult,
    DownstreamImpactSeverity,
    ImpactedSuccessorNode,
)
from app.schemas.risk import (
    ActivityRiskAssessment,
    RiskCategory,
    RiskSeverityLevel,
)
from app.schemas.variance import ActivityVarianceItem, ActivityVarianceStatus
from app.services.risk_service import risk_service

PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_cpm_node(
    act_id: UUID,
    code: str,
    total_float: int | None = 0,
    is_crit: bool = True,
    start: date | None = None,
    finish: date | None = None,
) -> CPMActivityNode:
    return CPMActivityNode(
        activity_id=act_id,
        project_id=PROJECT_ID,
        activity_code=code,
        name=f"Activity {code}",
        wbs_code="1.1",
        planned_start_date=start or date(2026, 1, 1),
        planned_finish_date=finish or date(2026, 1, 10),
        duration_days=10,
        early_start=start or date(2026, 1, 1),
        early_finish=finish or date(2026, 1, 10),
        late_start=start or date(2026, 1, 1),
        late_finish=finish or date(2026, 1, 10),
        total_float=total_float,
        free_float=total_float,
        is_critical=is_crit,
    )


def make_variance_item(
    act_id: UUID,
    code: str,
    status: ActivityVarianceStatus = ActivityVarianceStatus.IN_PROGRESS,
    date_var: int | None = 0,
    progress: float | None = 50.0,
) -> ActivityVarianceItem:
    return ActivityVarianceItem(
        activity_id=act_id,
        project_id=PROJECT_ID,
        activity_code=code,
        name=f"Activity {code}",
        planned_quantity=100.0,
        planned_unit="m3",
        planned_start_date=date(2026, 1, 1),
        planned_finish_date=date(2026, 1, 10),
        actual_quantity_total=50.0 if progress else None,
        actual_unit="m3",
        latest_actual_date=date(2026, 1, 10),
        approved_actuals_count=1,
        quantity_variance=0.0,
        progress_percent=progress,
        date_variance_days=date_var,
        variance_status=status,
        is_flagged=False,
    )


def make_downstream_result(
    src_id: UUID,
    src_code: str,
    delay: int = 0,
    trans_count: int = 0,
    successors: list[ImpactedSuccessorNode] | None = None,
) -> DownstreamImpactResult:
    succ_list = successors or []
    return DownstreamImpactResult(
        project_id=PROJECT_ID,
        source_activity_id=src_id,
        source_activity_code=src_code,
        source_name=f"Activity {src_code}",
        source_delay_days=delay,
        is_source_critical=True,
        total_downstream_activities_count=trans_count or len(succ_list),
        critical_slippage_count=0,
        buffer_absorbed_count=0,
        historical_completed_count=0,
        impacted_successors=succ_list,
    )


# ==============================================================================
# TESTS 1-8 — Canonical Category Classification
# ==============================================================================

def test_1_critical_path_delay_category():
    """Critical path activity (TF <= 0) with delay gets CRITICAL_PATH_DELAY."""
    cats = risk_service.classify_categories(
        is_critical_path=True,
        total_float=0,
        date_variance_days=3,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=1,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
    )
    assert RiskCategory.CRITICAL_PATH_DELAY in cats


def test_2_float_erosion_category():
    """Near-critical activity (0 < TF <= 3) with delay gets FLOAT_EROSION."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=2,
        date_variance_days=2,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=1,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
    )
    assert RiskCategory.FLOAT_EROSION in cats


def test_3_downstream_bottleneck_direct_successors():
    """At least 3 direct successors with delay gets DOWNSTREAM_BOTTLENECK."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=5,
        date_variance_days=2,
        is_past_due=False,
        direct_successors_count=3,
        transitive_successors_count=3,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
    )
    assert RiskCategory.DOWNSTREAM_BOTTLENECK in cats


def test_4_downstream_bottleneck_transitive_successors():
    """At least 5 transitive successors with delay gets DOWNSTREAM_BOTTLENECK."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=5,
        date_variance_days=2,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=6,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.IN_PROGRESS,
    )
    assert RiskCategory.DOWNSTREAM_BOTTLENECK in cats


def test_5_predecessor_blocker_category():
    """Blocked upstream predecessor gets PREDECESSOR_BLOCKER."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=5,
        date_variance_days=0,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=1,
        is_predecessor_blocked=True,
        variance_status=ActivityVarianceStatus.NOT_STARTED,
    )
    assert RiskCategory.PREDECESSOR_BLOCKER in cats


def test_6_unquantified_milestone_lag_category():
    """Unquantified milestone past due date gets UNQUANTIFIED_MILESTONE_LAG."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=4,
        date_variance_days=2,
        is_past_due=True,
        direct_successors_count=0,
        transitive_successors_count=0,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.UNQUANTIFIED,
    )
    assert RiskCategory.UNQUANTIFIED_MILESTONE_LAG in cats


def test_7_unit_mismatch_exposure_on_critical_activity():
    """Unit mismatch on critical/near-critical (TF <= 3) gets UNIT_MISMATCH_EXPOSURE."""
    cats = risk_service.classify_categories(
        is_critical_path=True,
        total_float=0,
        date_variance_days=0,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=1,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.UNIT_MISMATCH,
    )
    assert RiskCategory.UNIT_MISMATCH_EXPOSURE in cats


def test_8_unit_mismatch_on_safe_activity_not_exposed():
    """Unit mismatch on safe float activity (TF > 3) does NOT get UNIT_MISMATCH_EXPOSURE."""
    cats = risk_service.classify_categories(
        is_critical_path=False,
        total_float=10,
        date_variance_days=0,
        is_past_due=False,
        direct_successors_count=1,
        transitive_successors_count=1,
        is_predecessor_blocked=False,
        variance_status=ActivityVarianceStatus.UNIT_MISMATCH,
    )
    assert RiskCategory.UNIT_MISMATCH_EXPOSURE not in cats


# ==============================================================================
# TESTS 9-15 — Severity Precedence & Classification
# ==============================================================================

def test_9_overlapping_categories_coexist():
    """Activity can hold multiple risk categories simultaneously."""
    cats = risk_service.classify_categories(
        is_critical_path=True,
        total_float=0,
        date_variance_days=4,
        is_past_due=False,
        direct_successors_count=4,
        transitive_successors_count=6,
        is_predecessor_blocked=True,
        variance_status=ActivityVarianceStatus.UNIT_MISMATCH,
    )
    assert RiskCategory.CRITICAL_PATH_DELAY in cats
    assert RiskCategory.DOWNSTREAM_BOTTLENECK in cats
    assert RiskCategory.PREDECESSOR_BLOCKER in cats
    assert RiskCategory.UNIT_MISMATCH_EXPOSURE in cats


def test_10_critical_severity_precedence():
    """Critical path delay takes CRITICAL severity precedence."""
    sev = risk_service.classify_severity(
        is_critical_path=True,
        total_float=0,
        date_variance_days=3,
        is_past_due=False,
        transitive_successors_count=6,
        is_predecessor_blocked=True,
    )
    assert sev == RiskSeverityLevel.CRITICAL


def test_11_high_severity_near_critical_delay():
    """Near critical delay (0 < TF <= 3) gets HIGH severity."""
    sev = risk_service.classify_severity(
        is_critical_path=False,
        total_float=2,
        date_variance_days=2,
        is_past_due=False,
        transitive_successors_count=2,
        is_predecessor_blocked=False,
    )
    assert sev == RiskSeverityLevel.HIGH


def test_12_high_severity_transitive_fanout():
    """At least 5 transitive successors affected with delay gets HIGH severity."""
    sev = risk_service.classify_severity(
        is_critical_path=False,
        total_float=6,
        date_variance_days=2,
        is_past_due=False,
        transitive_successors_count=5,
        is_predecessor_blocked=False,
    )
    assert sev == RiskSeverityLevel.HIGH


def test_13_medium_severity_moderate_float_delay():
    """Moderate float (3 < TF <= 7) with delay gets MEDIUM severity."""
    sev = risk_service.classify_severity(
        is_critical_path=False,
        total_float=5,
        date_variance_days=2,
        is_past_due=False,
        transitive_successors_count=2,
        is_predecessor_blocked=False,
    )
    assert sev == RiskSeverityLevel.MEDIUM


def test_14_medium_severity_predecessor_blocker():
    """Blocked predecessor with safe float gets MEDIUM severity."""
    sev = risk_service.classify_severity(
        is_critical_path=False,
        total_float=10,
        date_variance_days=0,
        is_past_due=False,
        transitive_successors_count=1,
        is_predecessor_blocked=True,
    )
    assert sev == RiskSeverityLevel.MEDIUM


def test_15_low_severity_safe_float():
    """Safe float (TF > 7) with no delay gets LOW severity."""
    sev = risk_service.classify_severity(
        is_critical_path=False,
        total_float=12,
        date_variance_days=0,
        is_past_due=False,
        transitive_successors_count=1,
        is_predecessor_blocked=False,
    )
    assert sev == RiskSeverityLevel.LOW


# ==============================================================================
# TESTS 16-24 — Risk Score Mathematics (ADR-017)
# ==============================================================================

def test_16_score_lower_bound_is_zero():
    """Activity with high float (e.g. TF=20), no delay, no successors -> score 0."""
    score = risk_service.calculate_risk_score(
        is_critical_path=False,
        total_float=20,
        transitive_successors_count=0,
        date_variance_days=0,
    )
    assert score == 0


def test_17_score_upper_bound_is_100():
    """Critical path (40) + TF=0 (25) + >= 5 succ (20) + >= 5 days delay (15) -> 100."""
    score = risk_service.calculate_risk_score(
        is_critical_path=True,
        total_float=0,
        transitive_successors_count=10,
        date_variance_days=10,
    )
    assert score == 100


def test_18_critical_activity_contributes_40_points():
    """I_crit = 1 adds 40 points."""
    # TF=10 (S_float=0), succ=0 (S_fanout=0), delay=0 (S_delay=0)
    score = risk_service.calculate_risk_score(
        is_critical_path=True,
        total_float=10,
        transitive_successors_count=0,
        date_variance_days=0,
    )
    assert score == 40


def test_19_float_score_calculation():
    """S_float = max(0, 1 - TF/10) * 25."""
    # TF=6 -> S_float = 1 - 0.6 = 0.4 -> 25 * 0.4 = 10 pts
    score = risk_service.calculate_risk_score(
        is_critical_path=False,
        total_float=6,
        transitive_successors_count=0,
        date_variance_days=0,
    )
    assert score == 10


def test_20_fanout_score_calculation():
    """S_fanout = min(1.0, succ / 5) * 20."""
    # succ=3 -> S_fanout = 3/5 = 0.6 -> 20 * 0.6 = 12 pts
    score = risk_service.calculate_risk_score(
        is_critical_path=False,
        total_float=10,
        transitive_successors_count=3,
        date_variance_days=0,
    )
    assert score == 12


def test_21_delay_score_calculation_adr017():
    """S_delay = min(1.0, delay / 5) * 15."""
    # delay=3 -> S_delay = 3/5 = 0.6 -> 15 * 0.6 = 9 pts
    score = risk_service.calculate_risk_score(
        is_critical_path=False,
        total_float=10,
        transitive_successors_count=0,
        date_variance_days=3,
    )
    assert score == 9


def test_22_final_score_worked_example_1_adr017():
    """
    ADR-017 Worked Example 1:
      Critical (I_crit=1), TF=0 (S_float=1), 4 successors (S_fanout=0.8), 3 days delay (S_delay=0.6)
      40(1) + 25(1) + 20(0.8) + 15(0.6) = 40 + 25 + 16 + 9 = 90.
    """
    score = risk_service.calculate_risk_score(
        is_critical_path=True,
        total_float=0,
        transitive_successors_count=4,
        date_variance_days=3,
    )
    assert score == 90


def test_23_completed_activity_returns_zero_risk_score():
    """Completed activity has 0 risk score regardless of past dates."""
    score = risk_service.calculate_risk_score(
        is_critical_path=True,
        total_float=0,
        transitive_successors_count=5,
        date_variance_days=10,
        is_completed=True,
    )
    assert score == 0


def test_24_non_positive_delay_does_not_create_delay_risk():
    """Negative delay (early) or 0 delay results in S_delay = 0."""
    score_zero = risk_service.calculate_risk_score(False, 10, 0, 0)
    score_neg = risk_service.calculate_risk_score(False, 10, 0, -4)
    assert score_zero == 0
    assert score_neg == 0


# ==============================================================================
# TESTS 25-30 — System Integration & Boundary Checks
# ==============================================================================

def test_25_deterministic_project_risk_ordering():
    """
    Verify project risk assessment sorts items by:
      severity rank ASC (CRITICAL < HIGH < MEDIUM < LOW),
      risk_score DESC,
      activity_code ASC,
      activity_id ASC.
    """
    id1, id2, id3 = uuid4(), uuid4(), uuid4()
    cpm_nodes = [
        make_cpm_node(id1, "ACT-LOW", total_float=10, is_crit=False),
        make_cpm_node(id2, "ACT-CRIT-B", total_float=0, is_crit=True),
        make_cpm_node(id3, "ACT-CRIT-A", total_float=0, is_crit=True),
    ]
    cpm_res = CPMNetworkResult(
        project_id=PROJECT_ID,
        total_activities=3,
        critical_activities_count=2,
        nodes=cpm_nodes,
        critical_path=[id2, id3],
    )
    variance_items = [
        make_variance_item(id1, "ACT-LOW", date_var=0),
        make_variance_item(id2, "ACT-CRIT-B", date_var=5),  # 100 score
        make_variance_item(id3, "ACT-CRIT-A", date_var=5),  # 100 score
    ]
    downstream_map = {
        id1: make_downstream_result(id1, "ACT-LOW", 0, 0),
        id2: make_downstream_result(id2, "ACT-CRIT-B", 5, 5),
        id3: make_downstream_result(id3, "ACT-CRIT-A", 5, 5),
    }

    summary = risk_service.assess_project_risks(
        cpm_result=cpm_res,
        variance_items=variance_items,
        downstream_impact_map=downstream_map,
    )

    codes = [item.activity_code for item in summary.items]
    # ACT-CRIT-A comes before ACT-CRIT-B due to code ASC tie-breaking, followed by ACT-LOW
    assert codes == ["ACT-CRIT-A", "ACT-CRIT-B", "ACT-LOW"]


def test_26_extra_fields_rejected_by_schema():
    """Verify extra='forbid' prevents parameter tampering."""
    with pytest.raises(ValidationError):
        ActivityRiskAssessment(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Test",
            severity=RiskSeverityLevel.LOW,
            risk_score=10,
            tampered="forbidden",
        )


def test_27_invalid_enum_rejected():
    """Verify unknown severity level or category is rejected."""
    with pytest.raises(ValidationError):
        ActivityRiskAssessment(
            activity_id=uuid4(),
            project_id=PROJECT_ID,
            activity_code="ACT-101",
            name="Test",
            severity="INVALID_SEVERITY",  # type: ignore
            risk_score=10,
        )


def test_28_no_phase_9_5_api_identifiers_in_service():
    """Verify absence of API route signatures and DB handlers in domain service."""
    src = inspect.getsource(risk_service_mod)
    assert "@router" not in src
    assert "FastAPI" not in src
    assert "supabase" not in src
    assert "HTTPException" not in src


def test_29_no_forecasting_or_ml_logic():
    """Verify strictly deterministic math without probabilistic ML forecasting."""
    forbidden = ["random", "monte_carlo", "gaussian", "regression_model", "predict_delay"]
    src = inspect.getsource(risk_service_mod).lower()
    for token in forbidden:
        assert token not in src


def test_30_static_phase_boundary_check():
    """Scans Phase 9.4 modules and confirms ZERO occurrence of forbidden keywords."""
    forbidden_tokens = [
        "cpi",
        "spi",
        "cost_variance",
        "evm",
        "earned_value",
    ]
    modules = [risk_schemas, risk_service_mod]
    for mod in modules:
        src = inspect.getsource(mod).lower()
        for token in forbidden_tokens:
            assert token not in src, f"Forbidden token '{token}' found in {mod.__name__}"
