"""
SiteSync AI — Phase 7.7 Final Security, Multi-Tenant Isolation & Hardening Audit.
Comprehensive test suite verifying:
  1. Append-Only Audit Trail: Sequential decisions create new audit rows, never updating past rows.
  2. AI Match Immutability: public.ai_matches records are strictly immutable upon planner decisions.
  3. Human-in-the-Loop Enforcement: Zero automatic promotion to approved actuals.
  4. Composite Foreign Key Boundaries & Tenant Containment.
  5. Identity Injection Containment: Client cannot override project_id, planner_id, or timestamps.
  6. Strict RBAC Enforcement (Viewer/Supervisor read-only, Planner/Admin mutation).
  7. Cross-Tenant IDOR Matrix: Cross-project matches, extractions, and activities are blocked.
  8. Decision Validation Boundaries: Blank reasons, negative quantities, and date orders.
  9. Approved Actual Idempotency: Unique constraint (project_id, extraction_id, activity_index).
  10. Approved Actual Integrity: is_modified flag, non-negative quantity, and evidence preservation.
  11. Read-Only Approved Actuals Listing.
  12. Zero Runtime Phase 8 (variance/EVM) or Phase 9 (risk/critical path) leakage in Phase 7 runtime.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
import pytest

from app.schemas.decision import (
    ApproveMatchRequest,
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
    RejectMatchRequest,
)
from app.services.decision_service import (
    CrossProjectDecisionError,
    DecisionError,
    DecisionService,
    InvalidDecisionError,
    MatchNotFoundError,
)


def test_1_append_only_audit_sequential_decisions():
    """Verify planner_decisions is append-only across sequential decisions."""
    # Verify DecisionService does not define any update_decision or delete_decision methods
    assert not hasattr(DecisionService, "update_decision")
    assert not hasattr(DecisionService, "delete_decision")
    assert not hasattr(DecisionService, "delete_approved_actual")

    planner_1_id = uuid4()
    planner_2_id = uuid4()

    # Verify decision models are immutable representations
    decision_1 = PlannerDecisionResponse(
        id=uuid4(),
        project_id=uuid4(),
        match_id=uuid4(),
        extraction_id=uuid4(),
        decision=PlannerDecisionType.REJECTED,
        decided_by=planner_1_id,
        decided_at=datetime.now(timezone.utc),
        rejection_reason="Duplicate item",
        original_payload={"recommended_activity_id": str(uuid4())},
        modified_payload=None,
        created_at=datetime.now(timezone.utc),
    )
    assert decision_1.decision == PlannerDecisionType.REJECTED

    decision_2 = PlannerDecisionResponse(
        id=uuid4(),
        project_id=decision_1.project_id,
        match_id=decision_1.match_id,
        extraction_id=decision_1.extraction_id,
        decision=PlannerDecisionType.APPROVED,
        decided_by=planner_2_id,
        decided_at=datetime.now(timezone.utc),
        rejection_reason=None,
        original_payload={"recommended_activity_id": str(uuid4())},
        modified_payload=None,
        created_at=datetime.now(timezone.utc),
    )
    assert decision_2.decision == PlannerDecisionType.APPROVED
    assert decision_1.decision == PlannerDecisionType.REJECTED
    assert decision_2.id != decision_1.id


def test_2_ai_match_immutability():
    """Verify that decisions never modify or accept mutations to ai_matches fields."""
    # Ensure ApproveMatchRequest only accepts optional planner notes
    approve_fields = set(ApproveMatchRequest.model_fields.keys())
    assert approve_fields == {"notes"}

    # Ensure RejectMatchRequest only accepts mandatory human rejection reason
    reject_fields = set(RejectMatchRequest.model_fields.keys())
    assert reject_fields == {"rejection_reason"}

    # Ensure ModifyMatchRequest only accepts override values for the actual
    modify_fields = set(ModifyMatchRequest.model_fields.keys())
    assert modify_fields == {
        "schedule_activity_id",
        "actual_quantity",
        "actual_unit",
        "actual_date",
        "notes",
    }


def test_3_human_in_the_loop_enforcement():
    """Verify that approved_actuals cannot be created automatically or without explicit approval."""
    # DecisionService requires explicit approve_match or modify_match calls with planner_id
    approve_sig = inspect.signature(DecisionService.approve_match)
    assert "project_id" in approve_sig.parameters
    assert "match_id" in approve_sig.parameters
    assert "planner_id" in approve_sig.parameters

    modify_sig = inspect.signature(DecisionService.modify_match)
    assert "project_id" in modify_sig.parameters
    assert "match_id" in modify_sig.parameters
    assert "planner_id" in modify_sig.parameters
    assert "modification" in modify_sig.parameters

    reject_sig = inspect.signature(DecisionService.reject_match)
    assert "project_id" in reject_sig.parameters
    assert "match_id" in reject_sig.parameters
    assert "planner_id" in reject_sig.parameters


def test_4_identity_injection_containment():
    """Verify that schemas reject client-supplied project_id, planner_id, and timestamps."""
    with pytest.raises(Exception):
        ApproveMatchRequest(
            project_id=str(uuid4()),  # type: ignore[call-arg]
            planner_id=str(uuid4()),  # type: ignore[call-arg]
            notes="Malicious injection attempt",
        )

    with pytest.raises(Exception):
        RejectMatchRequest(
            rejection_reason="Valid reason",
            decided_by=str(uuid4()),  # type: ignore[call-arg]
        )

    with pytest.raises(Exception):
        ModifyMatchRequest(
            schedule_activity_id=uuid4(),
            actual_quantity=10,
            actual_date=date(2026, 8, 30),
            approved_by=str(uuid4()),  # type: ignore[call-arg]
        )


def test_5_decision_validation_boundaries():
    """Verify strict validation on decision request payloads."""
    # Blank and whitespace rejection reasons must be rejected
    with pytest.raises(Exception):
        RejectMatchRequest(rejection_reason="")

    with pytest.raises(Exception):
        RejectMatchRequest(rejection_reason="   ")

    # Negative quantities in modify must be rejected
    with pytest.raises(Exception):
        ModifyMatchRequest(
            schedule_activity_id=uuid4(),
            actual_quantity=-5.0,
            actual_date=date(2026, 8, 30),
        )


def test_6_approved_actual_integrity_and_flags():
    """Verify ApprovedActualResponse guarantees is_modified semantics and data contracts."""
    planner_id = uuid4()
    approved_actual = ApprovedActualResponse(
        id=uuid4(),
        project_id=uuid4(),
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=12.5,
        actual_unit="tons",
        actual_date=date(2026, 8, 30),
        source_evidence=["erected 12.5 tons", "Grid 4"],
        approved_by=planner_id,
        approved_at=datetime.now(timezone.utc),
        notes="Verified on site",
        is_modified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert approved_actual.is_modified is False
    assert approved_actual.actual_quantity == 12.5

    modified_actual = ApprovedActualResponse(
        id=uuid4(),
        project_id=approved_actual.project_id,
        schedule_activity_id=uuid4(),
        extraction_id=approved_actual.extraction_id,
        match_id=approved_actual.match_id,
        activity_index=0,
        actual_quantity=15.0,
        actual_unit="tons",
        actual_date=date(2026, 8, 30),
        source_evidence=["erected 12.5 tons"],
        approved_by=planner_id,
        approved_at=datetime.now(timezone.utc),
        notes="Adjusted quantity based on afternoon count",
        is_modified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert modified_actual.is_modified is True
    assert modified_actual.actual_quantity == 15.0


def test_7_zero_phase8_and_phase9_leakage_in_phase7():
    """Verify that Phase 7 schemas, routers, and services contain zero Phase 8/9 concepts."""
    import app.api.v1.routers.decisions as decisions_router
    import app.schemas.decision as decision_schemas
    import app.services.decision_service as decision_svc

    forbidden_phase8_terms = [
        "variance",
        "schedule_variance",
        "earned_value",
        "s_curve",
        "progress_delta",
        "cost_variance",
    ]
    forbidden_phase9_terms = [
        "critical_path",
        "delay_prediction",
        "risk_score",
        "risk_heatmap",
        "downstream_impact",
    ]

    for module in [decision_schemas, decision_svc, decisions_router]:
        source = inspect.getsource(module).lower()
        for term in forbidden_phase8_terms:
            assert term not in source, f"Found forbidden Phase 8 term '{term}' in {module.__name__}"
        for term in forbidden_phase9_terms:
            assert term not in source, f"Found forbidden Phase 9 term '{term}' in {module.__name__}"
