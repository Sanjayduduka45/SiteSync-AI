"""
SiteSync AI — Phase 8.1 Plan vs Actual Variance Domain Calculation Engine.
Pure, deterministic business logic implementing:
  - Activity-level variance calculations (ADR-009)
  - Multi-actual cumulative aggregation (ADR-010)
  - Unit compatibility and activity status lifecycle (ADR-011)
  - Homogeneous-unit WBS and Project rollups without percentage averaging (ADR-012)
  - Strict absence of arbitrary threshold flags or Phase 9 predictive logic (ADR-013)
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from app.schemas.variance import (
    ActivityVarianceInput,
    ActivityVarianceItem,
    ActivityVarianceStatus,
    ProjectVarianceSummary,
    UnitRollup,
    WbsRollup,
)


def normalize_unit(unit: str | None) -> str | None:
    """
    Normalizes a unit of measure string by stripping whitespace and lowercasing.
    Returns None if input is None or empty.
    """
    if unit is None:
        return None
    trimmed = unit.strip()
    return trimmed.lower() if trimmed else None


def are_units_compatible(unit1: str | None, unit2: str | None) -> bool:
    """
    Returns True if both units are non-empty and match after whitespace and case normalization.
    No automatic semantic conversion is performed (ADR-011).
    """
    norm1 = normalize_unit(unit1)
    norm2 = normalize_unit(unit2)
    if norm1 is None or norm2 is None:
        return False
    return norm1 == norm2


class VarianceService:
    """
    Pure domain service for Plan vs Actual variance calculations.
    Stateless, database-agnostic, and deterministic.
    """

    @staticmethod
    def calculate_activity_variance(item: ActivityVarianceInput) -> ActivityVarianceItem:
        """
        Calculates Plan vs Actual variance metrics for a single schedule activity.
        Strictly follows ADR-009, ADR-010, ADR-011, and ADR-013.
        """
        # ======================================================================
        # 1. Unquantified Activity Handling (Milestones / Qualitative Tasks)
        # ======================================================================
        if item.planned_quantity is None:
            approved_count = len(item.approved_actuals)
            latest_date = (
                max((act.actual_date for act in item.approved_actuals), default=None)
                if item.approved_actuals
                else None
            )

            date_var: int | None = None
            if latest_date is not None and item.planned_finish_date is not None:
                date_var = (latest_date - item.planned_finish_date).days

            return ActivityVarianceItem(
                activity_id=item.activity_id,
                project_id=item.project_id,
                activity_code=item.activity_code,
                name=item.name,
                wbs_code=item.wbs_code,
                discipline=item.discipline,
                location=item.location,
                planned_quantity=None,
                planned_unit=item.planned_unit,
                planned_start_date=item.planned_start_date,
                planned_finish_date=item.planned_finish_date,
                actual_quantity_total=None,
                actual_unit=None,
                latest_actual_date=latest_date,
                approved_actuals_count=approved_count,
                quantity_variance=None,
                progress_percent=None,
                date_variance_days=date_var,
                variance_status=ActivityVarianceStatus.UNQUANTIFIED,
                is_flagged=False,
                flag_reason=None,
            )

        # ======================================================================
        # 2. Quantified Activity with Zero Approved Actuals
        # ======================================================================
        if not item.approved_actuals:
            # ADR-009: quantity_variance = 0 - planned_quantity = -planned_quantity
            qty_var = -item.planned_quantity
            # ADR-009: progress_percent is NULL if planned_quantity == 0, else 0.0%
            prog_pct: float | None = 0.0 if item.planned_quantity > 0 else None

            return ActivityVarianceItem(
                activity_id=item.activity_id,
                project_id=item.project_id,
                activity_code=item.activity_code,
                name=item.name,
                wbs_code=item.wbs_code,
                discipline=item.discipline,
                location=item.location,
                planned_quantity=item.planned_quantity,
                planned_unit=item.planned_unit,
                planned_start_date=item.planned_start_date,
                planned_finish_date=item.planned_finish_date,
                actual_quantity_total=0.0,
                actual_unit=item.planned_unit,
                latest_actual_date=None,
                approved_actuals_count=0,
                quantity_variance=qty_var,
                progress_percent=prog_pct,
                date_variance_days=None,
                variance_status=ActivityVarianceStatus.NOT_STARTED,
                is_flagged=False,
                flag_reason=None,
            )

        # ======================================================================
        # 3. Unit Compatibility Check Across All Approved Actuals (ADR-011)
        # ======================================================================
        approved_count = len(item.approved_actuals)
        latest_date = max(act.actual_date for act in item.approved_actuals)

        date_var = None
        if latest_date is not None and item.planned_finish_date is not None:
            date_var = (latest_date - item.planned_finish_date).days

        # Verify every actual record with a unit matches the planned unit
        for actual in item.approved_actuals:
            if actual.actual_unit is not None and not are_units_compatible(
                actual.actual_unit, item.planned_unit
            ):
                return ActivityVarianceItem(
                    activity_id=item.activity_id,
                    project_id=item.project_id,
                    activity_code=item.activity_code,
                    name=item.name,
                    wbs_code=item.wbs_code,
                    discipline=item.discipline,
                    location=item.location,
                    planned_quantity=item.planned_quantity,
                    planned_unit=item.planned_unit,
                    planned_start_date=item.planned_start_date,
                    planned_finish_date=item.planned_finish_date,
                    actual_quantity_total=None,
                    actual_unit=actual.actual_unit,
                    latest_actual_date=latest_date,
                    approved_actuals_count=approved_count,
                    quantity_variance=None,
                    progress_percent=None,
                    date_variance_days=date_var,
                    variance_status=ActivityVarianceStatus.UNIT_MISMATCH,
                    is_flagged=False,
                    flag_reason=None,
                )

        # If planned unit is specified but actual units are missing on records with quantities
        if item.planned_unit is not None:
            for actual in item.approved_actuals:
                if actual.actual_quantity is not None and actual.actual_unit is None:
                    # Incompatible: planned unit required but actual has none
                    return ActivityVarianceItem(
                        activity_id=item.activity_id,
                        project_id=item.project_id,
                        activity_code=item.activity_code,
                        name=item.name,
                        wbs_code=item.wbs_code,
                        discipline=item.discipline,
                        location=item.location,
                        planned_quantity=item.planned_quantity,
                        planned_unit=item.planned_unit,
                        planned_start_date=item.planned_start_date,
                        planned_finish_date=item.planned_finish_date,
                        actual_quantity_total=None,
                        actual_unit=None,
                        latest_actual_date=latest_date,
                        approved_actuals_count=approved_count,
                        quantity_variance=None,
                        progress_percent=None,
                        date_variance_days=date_var,
                        variance_status=ActivityVarianceStatus.UNIT_MISMATCH,
                        is_flagged=False,
                        flag_reason=None,
                    )

        # ======================================================================
        # 4. Cumulative Quantity Aggregation (ADR-010)
        # ======================================================================
        actual_total = sum(
            act.actual_quantity
            for act in item.approved_actuals
            if act.actual_quantity is not None
        )

        # ADR-009: quantity_variance = actual_total - planned_quantity
        qty_var = actual_total - item.planned_quantity

        # ADR-009: progress_percent = (actual_total / planned_quantity) * 100
        # If planned_quantity is 0, progress_percent is NULL
        prog_pct = (
            (actual_total / item.planned_quantity) * 100.0
            if item.planned_quantity > 0
            else None
        )

        # ADR-011: Deterministic Activity Status Classification
        if actual_total == 0.0:
            status = ActivityVarianceStatus.NOT_STARTED
        elif actual_total < item.planned_quantity:
            status = ActivityVarianceStatus.IN_PROGRESS
        elif actual_total == item.planned_quantity:
            status = ActivityVarianceStatus.COMPLETED
        else:  # actual_total > item.planned_quantity
            status = ActivityVarianceStatus.OVER_DELIVERED

        return ActivityVarianceItem(
            activity_id=item.activity_id,
            project_id=item.project_id,
            activity_code=item.activity_code,
            name=item.name,
            wbs_code=item.wbs_code,
            discipline=item.discipline,
            location=item.location,
            planned_quantity=item.planned_quantity,
            planned_unit=item.planned_unit,
            planned_start_date=item.planned_start_date,
            planned_finish_date=item.planned_finish_date,
            actual_quantity_total=actual_total,
            actual_unit=item.planned_unit,
            latest_actual_date=latest_date,
            approved_actuals_count=approved_count,
            quantity_variance=qty_var,
            progress_percent=prog_pct,
            date_variance_days=date_var,
            variance_status=status,
            is_flagged=False,
            flag_reason=None,
        )

    @classmethod
    def calculate_wbs_rollups(
        cls, items: list[ActivityVarianceItem]
    ) -> list[WbsRollup]:
        """
        Aggregates activity variances by WBS tier.
        Physical quantities are aggregated strictly across homogeneous units (ADR-012).
        Unweighted averaging of activity percentages is strictly prohibited.
        """
        wbs_groups: dict[str, list[ActivityVarianceItem]] = defaultdict(list)
        for act in items:
            wbs = act.wbs_code or "UNASSIGNED"
            wbs_groups[wbs].append(act)

        result: list[WbsRollup] = []
        for wbs_code, act_list in wbs_groups.items():
            unquantified_count = 0
            unit_mismatch_count = 0

            # Group activities by normalized unit for physical rollups
            unit_subgroups: dict[str, list[ActivityVarianceItem]] = defaultdict(list)
            for act in act_list:
                if act.variance_status == ActivityVarianceStatus.UNQUANTIFIED:
                    unquantified_count += 1
                elif act.variance_status == ActivityVarianceStatus.UNIT_MISMATCH:
                    unit_mismatch_count += 1
                elif act.planned_unit is not None:
                    norm = normalize_unit(act.planned_unit) or "units"
                    unit_subgroups[norm].append(act)

            unit_rollups: list[UnitRollup] = []
            for _, subgroup in unit_subgroups.items():
                planned_sum = sum(
                    a.planned_quantity
                    for a in subgroup
                    if a.planned_quantity is not None
                )
                actual_sum = sum(
                    a.actual_quantity_total
                    for a in subgroup
                    if a.actual_quantity_total is not None
                )
                qty_variance = actual_sum - planned_sum
                progress_pct = (
                    (actual_sum / planned_sum) * 100.0 if planned_sum > 0 else None
                )
                display_unit = subgroup[0].planned_unit or "units"

                unit_rollups.append(
                    UnitRollup(
                        unit=display_unit,
                        planned_total=planned_sum,
                        actual_total=actual_sum,
                        quantity_variance=qty_variance,
                        progress_percent=progress_pct,
                        activity_count=len(subgroup),
                    )
                )

            result.append(
                WbsRollup(
                    wbs_code=wbs_code,
                    unit_rollups=unit_rollups,
                    unquantified_activity_count=unquantified_count,
                    unit_mismatch_activity_count=unit_mismatch_count,
                    total_activity_count=len(act_list),
                )
            )

        return sorted(result, key=lambda w: w.wbs_code)

    @classmethod
    def calculate_project_summary(
        cls, project_id: UUID, items: list[ActivityVarianceItem]
    ) -> ProjectVarianceSummary:
        """
        Computes project-wide plan vs actual variance summary.
        Aggregates homogeneous unit rollups and categorical status metrics without
        unweighted percentage averaging (ADR-012).
        """
        total_activities = len(items)
        activities_with_progress = 0
        completed_count = 0
        in_progress_count = 0
        not_started_count = 0
        over_delivered_count = 0
        unquantified_count = 0
        unit_mismatch_count = 0
        flagged_count = 0

        unit_subgroups: dict[str, list[ActivityVarianceItem]] = defaultdict(list)

        for act in items:
            if (act.actual_quantity_total or 0.0) > 0.0 or (
                act.approved_actuals_count > 0
                and act.variance_status
                not in (
                    ActivityVarianceStatus.NOT_STARTED,
                    ActivityVarianceStatus.UNIT_MISMATCH,
                )
            ):
                activities_with_progress += 1

            if act.variance_status == ActivityVarianceStatus.COMPLETED:
                completed_count += 1
            elif act.variance_status == ActivityVarianceStatus.IN_PROGRESS:
                in_progress_count += 1
            elif act.variance_status == ActivityVarianceStatus.NOT_STARTED:
                not_started_count += 1
            elif act.variance_status == ActivityVarianceStatus.OVER_DELIVERED:
                over_delivered_count += 1
            elif act.variance_status == ActivityVarianceStatus.UNQUANTIFIED:
                unquantified_count += 1
            elif act.variance_status == ActivityVarianceStatus.UNIT_MISMATCH:
                unit_mismatch_count += 1

            if act.is_flagged:
                flagged_count += 1

            if (
                act.variance_status
                not in (
                    ActivityVarianceStatus.UNQUANTIFIED,
                    ActivityVarianceStatus.UNIT_MISMATCH,
                )
                and act.planned_unit is not None
            ):
                norm = normalize_unit(act.planned_unit) or "units"
                unit_subgroups[norm].append(act)

        unit_rollups: list[UnitRollup] = []
        for _, subgroup in unit_subgroups.items():
            planned_sum = sum(
                a.planned_quantity for a in subgroup if a.planned_quantity is not None
            )
            actual_sum = sum(
                a.actual_quantity_total
                for a in subgroup
                if a.actual_quantity_total is not None
            )
            qty_variance = actual_sum - planned_sum
            progress_pct = (
                (actual_sum / planned_sum) * 100.0 if planned_sum > 0 else None
            )
            display_unit = subgroup[0].planned_unit or "units"

            unit_rollups.append(
                UnitRollup(
                    unit=display_unit,
                    planned_total=planned_sum,
                    actual_total=actual_sum,
                    quantity_variance=qty_variance,
                    progress_percent=progress_pct,
                    activity_count=len(subgroup),
                )
            )

        overall_progress = (
            unit_rollups[0].progress_percent if len(unit_rollups) == 1 else None
        )


        return ProjectVarianceSummary(
            project_id=project_id,
            total_activities=total_activities,
            activities_with_progress=activities_with_progress,
            completed_activities=completed_count,
            in_progress_activities=in_progress_count,
            not_started_activities=not_started_count,
            over_delivered_activities=over_delivered_count,
            unquantified_activities=unquantified_count,
            unit_mismatch_activities=unit_mismatch_count,
            flagged_variance_count=flagged_count,
            overall_progress_percent=overall_progress,
            unit_rollups=unit_rollups,
        )


variance_service = VarianceService()

