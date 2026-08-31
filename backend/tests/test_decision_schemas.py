"""
SiteSync AI — Phase 7.2 Decision Schemas Unit Tests.
Verifies Pydantic v2 validation rules, normalization, enum boundaries,
and strict rejection of unauthorized downstream fields (extra="forbid").
"""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError

from app.schemas.decision import (
    ApproveMatchRequest,
    ApprovedActualListResponse,
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
    RejectMatchRequest,
)


def test_1_valid_approve_request():
    """Verify ApproveMatchRequest with valid notes."""
    req = ApproveMatchRequest(notes="Verified on site morning walk")
    assert req.notes == "Verified on site morning walk"


def test_2_approve_request_omitted_notes():
    """Verify ApproveMatchRequest with omitted notes defaults to None."""
    req = ApproveMatchRequest()
    assert req.notes is None


def test_3_approve_whitespace_notes_normalization():
    """Verify whitespace-only notes normalizes to None."""
    req = ApproveMatchRequest(notes="   ")
    assert req.notes is None

    req_padded = ApproveMatchRequest(notes="  Approved with minor note  ")
    assert req_padded.notes == "Approved with minor note"


def test_4_unknown_approve_fields_rejected():
    """Verify extra='forbid' rejects client injection on ApproveMatchRequest."""
    with pytest.raises(ValidationError) as exc:
        ApproveMatchRequest.model_validate({
            "notes": "Valid note",
            "project_id": str(uuid4()),
        })
    assert "extra_forbidden" in str(exc.value)


def test_5_valid_reject_request():
    """Verify RejectMatchRequest with valid non-empty reason."""
    req = RejectMatchRequest(rejection_reason="Activity already completed in previous report")
    assert req.rejection_reason == "Activity already completed in previous report"


def test_6_missing_rejection_reason_rejected():
    """Verify missing rejection_reason fails validation."""
    with pytest.raises(ValidationError) as exc:
        RejectMatchRequest.model_validate({})
    assert "rejection_reason" in str(exc.value)


def test_7_blank_rejection_reason_rejected():
    """Verify empty string rejection_reason is rejected."""
    with pytest.raises(ValidationError) as exc:
        RejectMatchRequest(rejection_reason="")
    assert "must not be empty or whitespace only" in str(exc.value)


def test_8_whitespace_rejection_reason_rejected():
    """Verify whitespace-only rejection_reason is rejected."""
    with pytest.raises(ValidationError) as exc:
        RejectMatchRequest(rejection_reason="   \t\n  ")
    assert "must not be empty or whitespace only" in str(exc.value)


def test_9_unknown_reject_fields_rejected():
    """Verify extra='forbid' on RejectMatchRequest."""
    with pytest.raises(ValidationError) as exc:
        RejectMatchRequest.model_validate({
            "rejection_reason": "Valid reason",
            "decision": "rejected",
        })
    assert "extra_forbidden" in str(exc.value)


def test_10_valid_modify_request():
    """Verify ModifyMatchRequest with full valid fields."""
    act_id = uuid4()
    req = ModifyMatchRequest(
        schedule_activity_id=act_id,
        actual_quantity=15.5,
        actual_unit="spools",
        actual_date=date(2026, 8, 30),
        notes="Adjusted quantity from 10 to 15.5 spools",
    )
    assert req.schedule_activity_id == act_id
    assert req.actual_quantity == 15.5
    assert req.actual_unit == "spools"
    assert req.actual_date == date(2026, 8, 30)
    assert req.notes == "Adjusted quantity from 10 to 15.5 spools"


def test_11_invalid_uuid_rejected_in_modify():
    """Verify non-UUID string in schedule_activity_id fails validation."""
    with pytest.raises(ValidationError):
        ModifyMatchRequest.model_validate({
            "schedule_activity_id": "not-a-uuid",
            "actual_date": "2026-08-30",
        })


def test_12_negative_quantity_rejected_in_modify():
    """Verify negative actual_quantity fails ge=0.0 constraint."""
    with pytest.raises(ValidationError):
        ModifyMatchRequest(
            schedule_activity_id=uuid4(),
            actual_quantity=-1.0,
            actual_date=date(2026, 8, 30),
        )


def test_13_whitespace_actual_unit_normalization():
    """Verify whitespace-only actual_unit normalizes to None."""
    req = ModifyMatchRequest(
        schedule_activity_id=uuid4(),
        actual_unit="   ",
        actual_date=date(2026, 8, 30),
    )
    assert req.actual_unit is None


def test_14_whitespace_notes_normalization_in_modify():
    """Verify whitespace-only notes normalizes to None."""
    req = ModifyMatchRequest(
        schedule_activity_id=uuid4(),
        notes="   ",
        actual_date=date(2026, 8, 30),
    )
    assert req.notes is None


def test_15_unknown_modify_fields_rejected():
    """Verify extra='forbid' on ModifyMatchRequest."""
    with pytest.raises(ValidationError) as exc:
        ModifyMatchRequest.model_validate({
            "schedule_activity_id": str(uuid4()),
            "actual_date": "2026-08-30",
            "approved_by": str(uuid4()),
        })
    assert "extra_forbidden" in str(exc.value)


def test_16_valid_planner_decision_response():
    """Verify PlannerDecisionResponse serialization & types."""
    now = datetime.now(timezone.utc)
    res = PlannerDecisionResponse(
        id=uuid4(),
        project_id=uuid4(),
        match_id=uuid4(),
        extraction_id=uuid4(),
        decision=PlannerDecisionType.APPROVED,
        decided_by=uuid4(),
        decided_at=now,
        rejection_reason=None,
        original_payload={"recommended_activity_code": "ACT-1001"},
        modified_payload=None,
        created_at=now,
    )
    assert res.decision == PlannerDecisionType.APPROVED
    assert res.rejection_reason is None


def test_17_invalid_decision_enum_rejected():
    """Verify invalid string value for decision enum is rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        PlannerDecisionResponse.model_validate({
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "match_id": str(uuid4()),
            "extraction_id": str(uuid4()),
            "decision": "auto_approved",  # Invalid enum value
            "decided_by": str(uuid4()),
            "decided_at": now.isoformat(),
            "original_payload": {},
            "created_at": now.isoformat(),
        })


def test_18_valid_approved_actual_response():
    """Verify ApprovedActualResponse serialization & properties."""
    now = datetime.now(timezone.utc)
    res = ApprovedActualResponse(
        id=uuid4(),
        project_id=uuid4(),
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=25.0,
        actual_unit="LF",
        actual_date=date(2026, 8, 30),
        source_evidence=["installed 25 LF"],
        approved_by=uuid4(),
        approved_at=now,
        notes="Verified",
        is_modified=False,
        created_at=now,
        updated_at=now,
    )
    assert res.activity_index == 0
    assert res.actual_quantity == 25.0
    assert res.is_modified is False


def test_19_negative_activity_index_rejected():
    """Verify negative activity_index is rejected on ApprovedActualResponse."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ApprovedActualResponse(
            id=uuid4(),
            project_id=uuid4(),
            schedule_activity_id=uuid4(),
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=-1,
            actual_date=date(2026, 8, 30),
            approved_by=uuid4(),
            approved_at=now,
            created_at=now,
            updated_at=now,
        )


def test_20_negative_quantity_rejected_in_response():
    """Verify negative actual_quantity is rejected on ApprovedActualResponse."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ApprovedActualResponse(
            id=uuid4(),
            project_id=uuid4(),
            schedule_activity_id=uuid4(),
            extraction_id=uuid4(),
            match_id=uuid4(),
            activity_index=0,
            actual_quantity=-5.0,
            actual_date=date(2026, 8, 30),
            approved_by=uuid4(),
            approved_at=now,
            created_at=now,
            updated_at=now,
        )


def test_21_valid_approved_actual_list_response():
    """Verify ApprovedActualListResponse wrapper schema."""
    now = datetime.now(timezone.utc)
    item = ApprovedActualResponse(
        id=uuid4(),
        project_id=uuid4(),
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=10.0,
        actual_unit="units",
        actual_date=date(2026, 8, 30),
        source_evidence=[],
        approved_by=uuid4(),
        approved_at=now,
        created_at=now,
        updated_at=now,
    )
    res = ApprovedActualListResponse(
        items=[item],
        total=1,
        limit=50,
        offset=0,
    )
    assert len(res.items) == 1
    assert res.total == 1


def test_22_invalid_list_pagination_rejected():
    """Verify negative limit or offset fails validation."""
    with pytest.raises(ValidationError):
        ApprovedActualListResponse(
            items=[],
            total=0,
            limit=0,  # limit must be >= 1
            offset=0,
        )

    with pytest.raises(ValidationError):
        ApprovedActualListResponse(
            items=[],
            total=0,
            limit=50,
            offset=-1,  # offset must be >= 0
        )


def test_23_all_request_schemas_reject_identity_and_timestamp_injection():
    """Verify request models forbid client-supplied project_id, approved_by, decided_by, timestamps."""
    injected_fields = [
        "project_id",
        "match_id",
        "extraction_id",
        "approved_by",
        "decided_by",
        "approved_at",
        "decided_at",
        "created_at",
        "updated_at",
        "decision",
    ]

    for field in injected_fields:
        with pytest.raises(ValidationError):
            ApproveMatchRequest.model_validate({field: "injected"})

        with pytest.raises(ValidationError):
            RejectMatchRequest.model_validate({
                "rejection_reason": "valid reason",
                field: "injected",
            })

        with pytest.raises(ValidationError):
            ModifyMatchRequest.model_validate({
                "schedule_activity_id": str(uuid4()),
                "actual_date": "2026-08-30",
                field: "injected",
            })


def test_24_phase8_9_fields_rejected():
    """Verify unauthorized Phase 8/9 fields are rejected across all schemas."""
    downstream_fields = [
        "variance",
        "schedule_variance",
        "earned_value",
        "critical_path",
        "risk_score",
        "risk_level",
    ]

    for field in downstream_fields:
        with pytest.raises(ValidationError):
            ApproveMatchRequest.model_validate({field: 123})
        with pytest.raises(ValidationError):
            RejectMatchRequest.model_validate({"rejection_reason": "test", field: 123})
        with pytest.raises(ValidationError):
            ModifyMatchRequest.model_validate({
                "schedule_activity_id": str(uuid4()),
                "actual_date": "2026-08-30",
                field: 123,
            })
