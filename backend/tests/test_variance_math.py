"""
SiteSync AI — Phase 8.1 Plan vs Actual Mathematical Variance Engine Tests.
Comprehensive deterministic unit tests covering:
  - Quantity variance and sign conventions (ADR-009)
  - Progress percentage and un-clamped over-delivery (ADR-009)
  - Cumulative multiple actual aggregation (ADR-010)
  - Unit normalization and incompatibility handling (ADR-011)
  - Canonical activity status lifecycle (ADR-011)
  - Schedule finish date variance (ADR-009)
  - Homogeneous WBS and Project rollups without percentage averaging (ADR-012)
  - Static AST and token scan for Phase 9 boundary protection (ADR-013)
"""

from __future__ import annotations

import inspect
import pathlib
from datetime import date
from uuid import uuid4
import pytest

from app.schemas.variance import (
    ActivityVarianceInput,
    ActivityVarianceStatus,
    ApprovedActualInput,
)
from app.services.variance_service import (
    VarianceService,
    are_units_compatible,
    normalize_unit,
    variance_service,
)


@pytest.fixture
def make_input():
    """Helper fixture to construct ActivityVarianceInput easily."""
    def _maker(
        planned_qty: float | None = 100.0,
        planned_unit: str | None = "LF",
        planned_start: date | None = date(2026, 8, 1),
        planned_finish: date | None = date(2026, 8, 10),
        actuals: list[tuple[float | None, str | None, date]] | None = None,
        code: str = "ACT-101",
        wbs: str | None = "1.1",
    ) -> ActivityVarianceInput:
        approved = []
        if actuals is not None:
            for qty, unit, dt in actuals:
                approved.append(
                    ApprovedActualInput(
                        actual_quantity=qty,
                        actual_unit=unit,
                        actual_date=dt,
                    )
                )
        return ActivityVarianceInput(
            activity_id=uuid4(),
            project_id=uuid4(),
            activity_code=code,
            name=f"Activity {code}",
            wbs_code=wbs,
            discipline="Piping",
            location="Unit 1",
            planned_quantity=planned_qty,
            planned_unit=planned_unit,
            planned_start_date=planned_start,
            planned_finish_date=planned_finish,
            approved_actuals=approved,
        )
    return _maker


# ==============================================================================
# 1. Quantity Variance Tests (ADR-009)
# ==============================================================================

def test_1_quantity_variance_actual_below_planned(make_input):
    """Example 1: Planned 100 LF, Actual 80 LF -> Variance -20 LF (under plan)."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[(80.0, "LF", date(2026, 8, 5))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.quantity_variance == -20.0
    assert res.actual_quantity_total == 80.0
    assert res.variance_status == ActivityVarianceStatus.IN_PROGRESS


def test_2_quantity_variance_actual_equal_planned(make_input):
    """Planned 100 LF, Actual 100 LF -> Variance 0.0 LF (exact scope)."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[(100.0, "LF", date(2026, 8, 10))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.quantity_variance == 0.0
    assert res.actual_quantity_total == 100.0
    assert res.variance_status == ActivityVarianceStatus.COMPLETED


def test_3_quantity_variance_actual_above_planned(make_input):
    """Example 2: Planned 100 LF, Actual 120 LF -> Variance +20 LF (over plan)."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[(120.0, "LF", date(2026, 8, 12))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.quantity_variance == 20.0
    assert res.actual_quantity_total == 120.0
    assert res.variance_status == ActivityVarianceStatus.OVER_DELIVERED


# ==============================================================================
# 2. Progress Percentage Tests (ADR-009)
# ==============================================================================

def test_4_progress_percentage_normal(make_input):
    """Mandatory Example 1: 200 m3 planned, 100 m3 actual -> 50%."""
    inp = make_input(
        planned_qty=200.0,
        planned_unit="m3",
        actuals=[(100.0, "m3", date(2026, 8, 5))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.progress_percent == 50.0


def test_5_progress_percentage_exact_100(make_input):
    """100 tons planned, 100 tons actual -> 100%."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="tons",
        actuals=[(100.0, "tons", date(2026, 8, 8))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.progress_percent == 100.0


def test_6_progress_percentage_over_100_unclamped(make_input):
    """Mandatory Example 2: 100 m3 planned, 125 m3 actual -> 125% (unclamped)."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="m3",
        actuals=[(125.0, "m3", date(2026, 8, 9))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.progress_percent == 125.0


def test_7_progress_percentage_planned_zero(make_input):
    """Planned quantity == 0 -> progress_percent must be None (no division by zero)."""
    inp = make_input(
        planned_qty=0.0,
        planned_unit="LF",
        actuals=[(0.0, "LF", date(2026, 8, 5))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.progress_percent is None
    assert res.quantity_variance == 0.0


def test_8_progress_percentage_planned_null(make_input):
    """Planned quantity is None (milestone/unquantified) -> progress_percent and quantity_variance are None."""
    inp = make_input(
        planned_qty=None,
        planned_unit="LF",
        actuals=[(50.0, "LF", date(2026, 8, 5))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.progress_percent is None
    assert res.quantity_variance is None
    assert res.variance_status == ActivityVarianceStatus.UNQUANTIFIED


# ==============================================================================
# 3. Multiple Approved Actuals Accumulation Tests (ADR-010)
# ==============================================================================

def test_9_multiple_actuals_cumulative_sum(make_input):
    """Mandatory Example: 10 LF, 20 LF, 30 LF -> total 60 LF."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[
            (10.0, "LF", date(2026, 8, 2)),
            (20.0, "LF", date(2026, 8, 4)),
            (30.0, "LF", date(2026, 8, 7)),
        ],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.actual_quantity_total == 60.0
    assert res.quantity_variance == -40.0
    assert res.progress_percent == 60.0
    assert res.approved_actuals_count == 3


def test_10_multiple_actuals_second_example(make_input):
    """Second Mandatory Example: 10 LF, 20 LF, 25 LF -> total 55 LF."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[
            (10.0, "LF", date(2026, 8, 2)),
            (20.0, "LF", date(2026, 8, 4)),
            (25.0, "LF", date(2026, 8, 7)),
        ],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.actual_quantity_total == 55.0
    assert res.quantity_variance == -45.0
    assert res.progress_percent == pytest.approx(55.0)


def test_11_multiple_actuals_latest_date(make_input):
    """Latest work date must be MAX(actual_date)."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[
            (10.0, "LF", date(2026, 8, 12)),
            (20.0, "LF", date(2026, 8, 5)),
            (30.0, "LF", date(2026, 8, 8)),
        ],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.latest_actual_date == date(2026, 8, 12)


def test_12_multiple_actuals_null_quantity_ignored(make_input):
    """NULL actual quantities do not add to the sum but contribute to date/count."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[
            (20.0, "LF", date(2026, 8, 2)),
            (None, "LF", date(2026, 8, 9)),
            (30.0, "LF", date(2026, 8, 5)),
        ],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.actual_quantity_total == 50.0
    assert res.latest_actual_date == date(2026, 8, 9)
    assert res.approved_actuals_count == 3


def test_13_zero_actuals_returns_zero_actual_quantity(make_input):
    """Activity with zero actuals returns actual_quantity_total = 0.0."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.actual_quantity_total == 0.0
    assert res.quantity_variance == -100.0
    assert res.progress_percent == 0.0
    assert res.latest_actual_date is None
    assert res.approved_actuals_count == 0
    assert res.variance_status == ActivityVarianceStatus.NOT_STARTED


# ==============================================================================
# 4. Unit Compatibility Tests (ADR-011)
# ==============================================================================

def test_14_exact_unit_match(make_input):
    """Exact unit match 'LF' == 'LF' performs calculation."""
    inp = make_input(planned_qty=100.0, planned_unit="LF", actuals=[(40.0, "LF", date(2026, 8, 5))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.IN_PROGRESS
    assert res.progress_percent == 40.0


def test_15_case_insensitive_and_whitespace_unit_match(make_input):
    """Whitespace and case normalization: '  LF  ' == 'lf'."""
    assert are_units_compatible("  LF  ", "lf") is True
    inp = make_input(planned_qty=100.0, planned_unit="  LF  ", actuals=[(40.0, "lf", date(2026, 8, 5))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.IN_PROGRESS
    assert res.actual_quantity_total == 40.0


def test_16_incompatible_units_returns_unit_mismatch(make_input):
    """Planned in 'spools', actual in 'LF' -> UNIT_MISMATCH, quantity_variance = NULL."""
    inp = make_input(planned_qty=100.0, planned_unit="spools", actuals=[(40.0, "LF", date(2026, 8, 5))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.UNIT_MISMATCH
    assert res.quantity_variance is None
    assert res.progress_percent is None
    assert res.actual_quantity_total is None


def test_17_mixed_compatible_and_incompatible_actuals(make_input):
    """Planned 'LF', actuals contain 10 LF and 20 spools -> UNIT_MISMATCH."""
    inp = make_input(
        planned_qty=100.0,
        planned_unit="LF",
        actuals=[
            (10.0, "LF", date(2026, 8, 2)),
            (20.0, "spools", date(2026, 8, 4)),
        ],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.UNIT_MISMATCH
    assert res.quantity_variance is None
    assert res.progress_percent is None


# ==============================================================================
# 5. Activity Status Lifecycle Tests (ADR-011)
# ==============================================================================

def test_18_status_not_started_with_zero_actual(make_input):
    """actual_quantity_total == 0.0 -> NOT_STARTED."""
    inp = make_input(planned_qty=100.0, planned_unit="LF", actuals=[(0.0, "LF", date(2026, 8, 2))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.NOT_STARTED


def test_19_status_in_progress(make_input):
    """0 < actual < planned -> IN_PROGRESS."""
    inp = make_input(planned_qty=100.0, planned_unit="LF", actuals=[(45.0, "LF", date(2026, 8, 2))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.IN_PROGRESS


def test_20_status_completed(make_input):
    """actual == planned -> COMPLETED."""
    inp = make_input(planned_qty=100.0, planned_unit="LF", actuals=[(100.0, "LF", date(2026, 8, 2))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.COMPLETED


def test_21_status_over_delivered(make_input):
    """actual > planned -> OVER_DELIVERED."""
    inp = make_input(planned_qty=100.0, planned_unit="LF", actuals=[(130.0, "LF", date(2026, 8, 2))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.OVER_DELIVERED


def test_22_status_unquantified(make_input):
    """planned_quantity is None -> UNQUANTIFIED."""
    inp = make_input(planned_qty=None, planned_unit=None, actuals=[])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.UNQUANTIFIED


def test_23_status_unit_mismatch(make_input):
    """Incompatible unit -> UNIT_MISMATCH."""
    inp = make_input(planned_qty=50.0, planned_unit="LF", actuals=[(50.0, "tons", date(2026, 8, 2))])
    res = variance_service.calculate_activity_variance(inp)
    assert res.variance_status == ActivityVarianceStatus.UNIT_MISMATCH


# ==============================================================================
# 6. Date / Schedule Variance Tests (ADR-009)
# ==============================================================================

def test_24_date_variance_early(make_input):
    """Example 2: Planned finish 2026-08-10, Latest actual 2026-08-08 -> -2 days (early)."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=date(2026, 8, 10),
        actuals=[(100.0, "LF", date(2026, 8, 8))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.date_variance_days == -2


def test_25_date_variance_on_time(make_input):
    """Planned finish 2026-08-10, Latest actual 2026-08-10 -> 0 days (on time)."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=date(2026, 8, 10),
        actuals=[(100.0, "LF", date(2026, 8, 10))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.date_variance_days == 0


def test_26_date_variance_late(make_input):
    """Example 1: Planned finish 2026-08-10, Latest actual 2026-08-13 -> +3 days (late)."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=date(2026, 8, 10),
        actuals=[(100.0, "LF", date(2026, 8, 13))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.date_variance_days == 3


def test_27_date_variance_missing_planned_finish(make_input):
    """Planned finish is None -> date_variance_days is None."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=None,
        actuals=[(100.0, "LF", date(2026, 8, 13))],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.date_variance_days is None


def test_28_date_variance_missing_actual_date_when_no_actuals(make_input):
    """No approved actuals -> date_variance_days is None."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=date(2026, 8, 10),
        actuals=[],
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.date_variance_days is None


# ==============================================================================
# 7. Rollups & Prohibition of Percentage Averaging Tests (ADR-012)
# ==============================================================================

def test_29_homogeneous_wbs_rollup(make_input):
    """
    Mandatory Example:
    WBS 1.2:
      Activity A: 100 LF planned, 50 LF actual
      Activity B: 200 LF planned, 100 LF actual
    WBS Rollup:
      Planned = 300 LF
      Actual = 150 LF
      Progress = 50%
      Quantity Variance = -150 LF
    """
    act_a = variance_service.calculate_activity_variance(
        make_input(planned_qty=100.0, planned_unit="LF", actuals=[(50.0, "LF", date(2026, 8, 1))], code="A", wbs="1.2")
    )
    act_b = variance_service.calculate_activity_variance(
        make_input(planned_qty=200.0, planned_unit="LF", actuals=[(100.0, "LF", date(2026, 8, 2))], code="B", wbs="1.2")
    )

    wbs_list = variance_service.calculate_wbs_rollups([act_a, act_b])
    assert len(wbs_list) == 1
    wbs = wbs_list[0]
    assert wbs.wbs_code == "1.2"
    assert len(wbs.unit_rollups) == 1

    unit_r = wbs.unit_rollups[0]
    assert unit_r.unit == "LF"
    assert unit_r.planned_total == 300.0
    assert unit_r.actual_total == 150.0
    assert unit_r.quantity_variance == -150.0
    assert unit_r.progress_percent == 50.0
    assert unit_r.activity_count == 2


def test_30_mixed_unit_wbs_separation(make_input):
    """
    Mandatory Example 2:
    WBS 1.2:
      Activity A: 100 LF planned, 50 LF actual
      Activity B: 50 tons planned, 25 tons actual
    Must provide SEPARATE LF and tons rollups without combining them into 150 'units'.
    """
    act_a = variance_service.calculate_activity_variance(
        make_input(planned_qty=100.0, planned_unit="LF", actuals=[(50.0, "LF", date(2026, 8, 1))], code="A", wbs="1.2")
    )
    act_b = variance_service.calculate_activity_variance(
        make_input(planned_qty=50.0, planned_unit="tons", actuals=[(25.0, "tons", date(2026, 8, 2))], code="B", wbs="1.2")
    )

    wbs_list = variance_service.calculate_wbs_rollups([act_a, act_b])
    wbs = wbs_list[0]
    assert len(wbs.unit_rollups) == 2

    units = {u.unit: u for u in wbs.unit_rollups}
    assert "LF" in units
    assert units["LF"].planned_total == 100.0
    assert units["LF"].actual_total == 50.0
    assert "tons" in units
    assert units["tons"].planned_total == 50.0
    assert units["tons"].actual_total == 25.0


def test_31_project_summary_homogeneous_and_mixed(make_input):
    """Verify ProjectVarianceSummary computes clean status counts and unit rollups."""
    proj_id = uuid4()
    act1 = variance_service.calculate_activity_variance(
        make_input(planned_qty=100.0, planned_unit="LF", actuals=[(100.0, "LF", date(2026, 8, 1))], code="A")
    )
    act2 = variance_service.calculate_activity_variance(
        make_input(planned_qty=200.0, planned_unit="LF", actuals=[(50.0, "LF", date(2026, 8, 2))], code="B")
    )
    act3 = variance_service.calculate_activity_variance(
        make_input(planned_qty=None, planned_unit=None, actuals=[], code="C")
    )
    act4 = variance_service.calculate_activity_variance(
        make_input(planned_qty=50.0, planned_unit="LF", actuals=[(10.0, "spools", date(2026, 8, 3))], code="D")
    )

    summary = variance_service.calculate_project_summary(proj_id, [act1, act2, act3, act4])
    assert summary.total_activities == 4
    assert summary.completed_activities == 1  # act1
    assert summary.in_progress_activities == 1  # act2
    assert summary.unquantified_activities == 1  # act3
    assert summary.unit_mismatch_activities == 1  # act4
    assert summary.flagged_variance_count == 0

    # Only act1 and act2 have valid LF quantities
    assert len(summary.unit_rollups) == 1
    assert summary.unit_rollups[0].unit == "LF"
    assert summary.unit_rollups[0].planned_total == 300.0
    assert summary.unit_rollups[0].actual_total == 150.0
    assert summary.unit_rollups[0].progress_percent == 50.0


# ==============================================================================
# 8. Variance Flagging Policy (ADR-013)
# ==============================================================================

def test_32_variance_flagging_is_false_by_default(make_input):
    """Per ADR-013: is_flagged is strictly False by default. No arbitrary thresholds."""
    inp = make_input(
        planned_qty=100.0,
        planned_finish=date(2026, 8, 1),
        actuals=[(10.0, "LF", date(2026, 8, 30))],  # 10% progress and 29 days late
    )
    res = variance_service.calculate_activity_variance(inp)
    assert res.is_flagged is False
    assert res.flag_reason is None


# ==============================================================================
# 9. Phase 9 Boundary Static Test (ADR-013)
# ==============================================================================

def test_33_phase9_boundary_static_check():
    """
    Static AST / Source inspection verifying zero Phase 9 concepts exist
    in Phase 8.1 runtime schemas or services.
    Forbidden concepts:
      - critical_path
      - float (as domain metric/slack, not python type)
      - slack
      - delay_prediction
      - forecast
      - forecasting
      - risk_score
      - risk_level
      - risk_heatmap
      - downstream_impact
    """
    import app.schemas.variance as var_schemas
    import app.services.variance_service as var_serv

    schema_source = inspect.getsource(var_schemas)
    serv_source = inspect.getsource(var_serv)

    forbidden_tokens = [
        "critical_path",
        "delay_prediction",
        "delay_forecast",
        "forecasting",
        "risk_score",
        "risk_level",
        "risk_heatmap",
        "downstream_impact",
        "total_float",
        "free_float",
        "slack_days",
    ]

    for token in forbidden_tokens:
        assert token not in schema_source.lower(), f"Forbidden Phase 9 token '{token}' in schemas/variance.py"
        assert token not in serv_source.lower(), f"Forbidden Phase 9 token '{token}' in services/variance_service.py"
