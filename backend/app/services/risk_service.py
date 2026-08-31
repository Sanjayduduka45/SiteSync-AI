"""
SiteSync AI — Phase 9.4 Risk Intelligence & Severity Pure Domain Engine.
Stateless, database-agnostic business logic implementing:
  - Canonical 6-category risk taxonomy assignment (ADR-017)
  - 4-level deterministic severity classification with explicit precedence (ADR-017)
  - Transparent composite risk score calculation [0-100] (ADR-017)
  - Multi-source input boundary integration (Phase 8 variance, Phase 9.2 CPM, Phase 9.3 downstream impact)
  - Completed activity historical safety and deterministic output sorting
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.schemas.cpm import CPMActivityNode, CPMNetworkResult
from app.schemas.downstream_impact import DownstreamImpactResult
from app.schemas.risk import (
    ActivityRiskAssessment,
    ProjectRiskSummary,
    RiskCategory,
    RiskSeverityLevel,
)
from app.schemas.variance import ActivityVarianceItem, ActivityVarianceStatus
from app.services.cpm_service import CPMValidationError


class RiskService:
    """
    Pure domain service for schedule risk intelligence and severity calculation.
    Consumes pre-computed Phase 8 variance, Phase 9.2 CPM, and Phase 9.3 downstream impact results.
    """

    @staticmethod
    def calculate_risk_score(
        is_critical_path: bool,
        total_float: int | None,
        transitive_successors_count: int,
        date_variance_days: int | None,
        is_completed: bool = False,
    ) -> int:
        """
        Calculates deterministic composite integer risk score [0-100] (ADR-017):
          Risk Score = min(100, round(40 * I_crit + 25 * S_float + 20 * S_fanout + 15 * S_delay))
        """
        if is_completed:
            return 0

        # 1. Critical path factor (Weight: 40)
        i_crit = 1.0 if is_critical_path else 0.0

        # 2. Float factor (Weight: 25)
        # S_float = max(0, 1 - TF/10) for TF >= 0, and 1.0 for TF < 0
        if total_float is None:
            s_float = 1.0 if is_critical_path else 0.0
        elif total_float < 0:
            s_float = 1.0
        else:
            s_float = max(0.0, 1.0 - (total_float / 10.0))

        # 3. Fan-out factor (Weight: 20)
        # S_fanout = min(1.0, transitive_successors / 5)
        s_fanout = min(1.0, max(0, transitive_successors_count) / 5.0)

        # 4. Delay factor (Weight: 15)
        # S_delay = min(1.0, max(0, ΔT) / 5)
        delta_t = max(0, date_variance_days) if date_variance_days is not None else 0
        s_delay = min(1.0, delta_t / 5.0)

        raw_score = (40.0 * i_crit) + (25.0 * s_float) + (20.0 * s_fanout) + (15.0 * s_delay)
        return min(100, max(0, round(raw_score)))

    @staticmethod
    def classify_categories(
        is_critical_path: bool,
        total_float: int | None,
        date_variance_days: int | None,
        is_past_due: bool,
        direct_successors_count: int,
        transitive_successors_count: int,
        is_predecessor_blocked: bool,
        variance_status: ActivityVarianceStatus | None,
        is_completed: bool = False,
    ) -> list[RiskCategory]:
        """
        Assigns all active canonical risk categories applicable to the activity (ADR-017).
        Multiple categories can coexist.
        """
        if is_completed:
            return []

        categories: list[RiskCategory] = []
        has_delay = (date_variance_days is not None and date_variance_days > 0) or is_past_due
        tf_val = total_float if total_float is not None else 0

        # 1. CRITICAL_PATH_DELAY: Critical path activity (TF <= 0) with factual delay/lag
        if is_critical_path and has_delay:
            categories.append(RiskCategory.CRITICAL_PATH_DELAY)

        # 2. FLOAT_EROSION: Near-critical activity (0 < TF <= 3) with delay
        if total_float is not None and 0 < total_float <= 3 and has_delay:
            categories.append(RiskCategory.FLOAT_EROSION)

        # 3. DOWNSTREAM_BOTTLENECK: Delayed activity with >=3 direct or >=5 transitive successors
        if has_delay and (direct_successors_count >= 3 or transitive_successors_count >= 5):
            categories.append(RiskCategory.DOWNSTREAM_BOTTLENECK)

        # 4. PREDECESSOR_BLOCKER: Activity cannot start/proceed because an upstream predecessor is blocked/delayed
        if is_predecessor_blocked:
            categories.append(RiskCategory.PREDECESSOR_BLOCKER)

        # 5. UNQUANTIFIED_MILESTONE_LAG: Unquantified milestone past due date
        if variance_status == ActivityVarianceStatus.UNQUANTIFIED and has_delay:
            categories.append(RiskCategory.UNQUANTIFIED_MILESTONE_LAG)

        # 6. UNIT_MISMATCH_EXPOSURE: Unit mismatch on critical or near-critical activity (TF <= 3)
        if variance_status == ActivityVarianceStatus.UNIT_MISMATCH and (is_critical_path or tf_val <= 3):
            categories.append(RiskCategory.UNIT_MISMATCH_EXPOSURE)

        return categories

    @staticmethod
    def classify_severity(
        is_critical_path: bool,
        total_float: int | None,
        date_variance_days: int | None,
        is_past_due: bool,
        transitive_successors_count: int,
        is_predecessor_blocked: bool,
        progress_lag: bool = False,
        is_completed: bool = False,
    ) -> RiskSeverityLevel:
        """
        Determines discrete severity level with strict canonical precedence (ADR-017):
          CRITICAL > HIGH > MEDIUM > LOW
        """
        if is_completed:
            return RiskSeverityLevel.LOW

        has_delay = (date_variance_days is not None and date_variance_days > 0) or is_past_due
        tf_val = total_float if total_float is not None else 0

        # CRITICAL: On Critical Path (TF <= 0) AND (ΔT > 0 OR past planned finish)
        if is_critical_path and has_delay:
            return RiskSeverityLevel.CRITICAL

        # HIGH: (0 < TF <= 3 AND delay) OR (>= 5 transitive successors impacted with delay)
        if (total_float is not None and 0 < total_float <= 3 and has_delay) or (transitive_successors_count >= 5 and has_delay):
            return RiskSeverityLevel.HIGH

        # MEDIUM: (3 < TF <= 7 with delay or progress lag) OR (non-critical predecessor is blocked)
        if (total_float is not None and 3 < total_float <= 7 and (has_delay or progress_lag)) or is_predecessor_blocked:
            return RiskSeverityLevel.MEDIUM

        # LOW: Default (TF > 7 with minor/zero variance, or on-track activity)
        return RiskSeverityLevel.LOW

    @staticmethod
    def assess_project_risks(
        cpm_result: CPMNetworkResult,
        variance_items: list[ActivityVarianceItem],
        downstream_impact_map: dict[UUID, DownstreamImpactResult],
        direct_successors_count_map: dict[UUID, int] | None = None,
        current_date: date | None = None,
    ) -> ProjectRiskSummary:
        """
        Executes comprehensive project-level risk assessment integrating CPM, Phase 8 Variances,
        and Phase 9.3 Downstream Impacts.
        """
        eval_date = current_date or date.today()
        variance_map = {v.activity_id: v for v in variance_items}
        direct_succ_map = direct_successors_count_map or {}

        # Pre-calculate which activities have delayed predecessors
        delayed_predecessor_targets: set[UUID] = set()
        for src_id, impact_res in downstream_impact_map.items():
            if impact_res.source_delay_days > 0:
                for succ in impact_res.impacted_successors:
                    delayed_predecessor_targets.add(succ.activity_id)

        assessments: list[ActivityRiskAssessment] = []

        for node in cpm_result.nodes:
            act_id = node.activity_id
            v_item = variance_map.get(act_id)
            impact_res = downstream_impact_map.get(act_id)

            # Phase 8 status & completion check
            v_status = v_item.variance_status if v_item else None
            is_comp = v_status == ActivityVarianceStatus.COMPLETED

            # Date variance & past due checks
            d_var = v_item.date_variance_days if v_item else None
            is_past_due = False
            if not is_comp and node.planned_finish_date is not None:
                is_past_due = eval_date > node.planned_finish_date

            # Successor counts from Phase 9.3 downstream impact
            trans_succ_count = impact_res.total_downstream_activities_count if impact_res else 0
            crit_slip_count = impact_res.critical_slippage_count if impact_res else 0
            dir_succ_count = direct_succ_map.get(act_id, 0)

            is_pred_blocked = act_id in delayed_predecessor_targets and not is_comp

            # Progress lag check (e.g. progress < 50% past timeline midpoint)
            progress_pct = v_item.progress_percent if v_item else None
            progress_lag = False
            if progress_pct is not None and progress_pct < 50.0 and is_past_due:
                progress_lag = True

            # Classify severity
            severity = RiskService.classify_severity(
                is_critical_path=node.is_critical,
                total_float=node.total_float,
                date_variance_days=d_var,
                is_past_due=is_past_due,
                transitive_successors_count=trans_succ_count,
                is_predecessor_blocked=is_pred_blocked,
                progress_lag=progress_lag,
                is_completed=is_comp,
            )

            # Calculate composite risk score
            score = RiskService.calculate_risk_score(
                is_critical_path=node.is_critical,
                total_float=node.total_float,
                transitive_successors_count=trans_succ_count,
                date_variance_days=d_var,
                is_completed=is_comp,
            )

            # Assign active risk categories
            categories = RiskService.classify_categories(
                is_critical_path=node.is_critical,
                total_float=node.total_float,
                date_variance_days=d_var,
                is_past_due=is_past_due,
                direct_successors_count=dir_succ_count,
                transitive_successors_count=trans_succ_count,
                is_predecessor_blocked=is_pred_blocked,
                variance_status=v_status,
                is_completed=is_comp,
            )

            assessments.append(
                ActivityRiskAssessment(
                    activity_id=act_id,
                    project_id=node.project_id,
                    activity_code=node.activity_code,
                    name=node.name,
                    wbs_code=node.wbs_code,
                    discipline=node.discipline,
                    location=node.location,
                    severity=severity,
                    risk_score=score,
                    categories=categories,
                    is_critical_path=node.is_critical,
                    total_float=node.total_float,
                    date_variance_days=d_var,
                    direct_successors_count=dir_succ_count,
                    transitive_successors_count=trans_succ_count,
                    critical_slippage_successors_count=crit_slip_count,
                    variance_status=v_status,
                    progress_percent=progress_pct,
                    is_completed=is_comp,
                )
            )

        # Deterministic sorting: severity rank (CRITICAL < HIGH < MEDIUM < LOW), risk_score DESC, activity_code ASC, activity_id ASC
        severity_rank = {
            RiskSeverityLevel.CRITICAL: 0,
            RiskSeverityLevel.HIGH: 1,
            RiskSeverityLevel.MEDIUM: 2,
            RiskSeverityLevel.LOW: 3,
        }
        assessments.sort(
            key=lambda a: (severity_rank[a.severity], -a.risk_score, a.activity_code, str(a.activity_id))
        )

        # Aggregate counts
        crit_count = sum(1 for a in assessments if a.severity == RiskSeverityLevel.CRITICAL)
        high_count = sum(1 for a in assessments if a.severity == RiskSeverityLevel.HIGH)
        med_count = sum(1 for a in assessments if a.severity == RiskSeverityLevel.MEDIUM)
        low_count = sum(1 for a in assessments if a.severity == RiskSeverityLevel.LOW)

        cp_delay_count = sum(1 for a in assessments if RiskCategory.CRITICAL_PATH_DELAY in a.categories)
        float_erosion_count = sum(1 for a in assessments if RiskCategory.FLOAT_EROSION in a.categories)
        bottleneck_count = sum(1 for a in assessments if RiskCategory.DOWNSTREAM_BOTTLENECK in a.categories)
        pred_blocker_count = sum(1 for a in assessments if RiskCategory.PREDECESSOR_BLOCKER in a.categories)
        milestone_lag_count = sum(1 for a in assessments if RiskCategory.UNQUANTIFIED_MILESTONE_LAG in a.categories)
        mismatch_count = sum(1 for a in assessments if RiskCategory.UNIT_MISMATCH_EXPOSURE in a.categories)

        active_scores = [a.risk_score for a in assessments if not a.is_completed]
        avg_score = round(sum(active_scores) / len(active_scores), 1) if active_scores else None

        return ProjectRiskSummary(
            project_id=cpm_result.project_id,
            total_activities=len(assessments),
            critical_severity_count=crit_count,
            high_severity_count=high_count,
            medium_severity_count=med_count,
            low_severity_count=low_count,
            critical_path_delay_count=cp_delay_count,
            float_erosion_count=float_erosion_count,
            downstream_bottleneck_count=bottleneck_count,
            predecessor_blocker_count=pred_blocker_count,
            unquantified_milestone_lag_count=milestone_lag_count,
            unit_mismatch_exposure_count=mismatch_count,
            average_risk_score=avg_score,
            items=assessments,
        )


risk_service = RiskService()
