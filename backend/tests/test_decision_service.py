"""
SiteSync AI — Phase 7.3 Decision Service & Repositories Unit Tests.
Verifies domain logic, append-only audit trail, idempotent approved actuals creation,
strict project isolation, and immutability of original AI match recommendations.
"""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4
import pytest

from app.schemas.decision import (
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
)
from app.schemas.schedule import (
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScoringBreakdown,
)
from app.services.decision_service import (
    ApprovedActualRepository,
    CrossProjectDecisionError,
    DecisionService,
    ExtractionNotFoundError,
    InvalidDecisionError,
    MatchNotFoundError,
    PlannerDecisionRepository,
    ScheduleActivityNotFoundError,
)
from app.services.extraction_service import AIExtractionRepository, extraction_service
from app.services.matching_service import AIMatchRepository, matching_service
from app.services.schedule_service import ScheduleService, schedule_service


@pytest.fixture
def decision_fixture():
    """Sets up a clean test fixture with mock repositories."""
    proj_id = uuid4()
    planner_id = uuid4()
    sched_act_id = uuid4()
    alt_act_id = uuid4()
    ext_id = uuid4()
    match_id = uuid4()

    # Clear repos
    decision_repo = PlannerDecisionRepository()
    decision_repo.clear()
    actual_repo = ApprovedActualRepository()
    actual_repo.clear()
    match_repo = AIMatchRepository()
    match_repo.clear()
    schedule_svc = ScheduleService()
    schedule_svc.clear()
    ext_svc = extraction_service
    ext_svc.repository = AIExtractionRepository()

    # Seed baseline schedule activities
    schedule_svc._activities[str(sched_act_id)] = {
        "id": str(sched_act_id),
        "project_id": str(proj_id),
        "activity_code": "ACT-1001",
        "name": "Erect Structural Steel Tier 1",
        "wbs_code": "1.2.1",
        "discipline": "Civil",
        "location": "Grid 4",
        "planned_start_date": date(2026, 9, 1),
        "planned_finish_date": date(2026, 9, 15),
        "planned_quantity": 250.0,
        "planned_unit": "tons",
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    schedule_svc._activities[str(alt_act_id)] = {
        "id": str(alt_act_id),
        "project_id": str(proj_id),
        "activity_code": "ACT-2002",
        "name": "Install Underground Sewer Pipe",
        "wbs_code": "2.1.3",
        "discipline": "Piping",
        "location": "Zone B",
        "planned_start_date": date(2026, 9, 5),
        "planned_finish_date": date(2026, 9, 20),
        "planned_quantity": 500.0,
        "planned_unit": "LF",
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    # Seed extraction
    ext_svc.repository._records_by_id[str(ext_id)] = {
        "id": str(ext_id),
        "project_id": str(proj_id),
        "field_input_id": str(uuid4()),
        "status": "completed",
        "extracted_data": {
            "raw_input_id": "inp-1",
            "extracted_activities": [
                {
                    "description": "Erected 10 spools in Grid 4",
                    "progress_value": 10.0,
                    "progress_unit": "spools",
                    "discipline": "Civil",
                    "location": "Grid 4",
                    "event_date": "2026-08-30",
                    "evidence_tokens": ["erected 10 spools", "Grid 4"],
                }
            ],
            "extraction_confidence": 0.95,
            "model_version": "gemini-1.5-flash:v1",
        },
        "confidence_score": 0.95,
        "model_version": "gemini-1.5-flash:v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Seed AI match recommendation
    match_rec = MatchRecommendationResponse(
        id=match_id,
        project_id=proj_id,
        extraction_id=ext_id,
        activity_index=0,
        recommended_activity_id=sched_act_id,
        recommended_activity_code="ACT-1001",
        recommended_activity_name="Erect Structural Steel Tier 1",
        confidence_score=0.94,
        scoring_breakdown=ScoringBreakdown(
            semantic_similarity=0.95,
            discipline_contribution=0.15,
            location_contribution=0.10,
            temporal_contribution=0.05,
        ),
        alternative_matches=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    match_repo._matches[(str(proj_id), str(ext_id), 0)] = {
        "id": match_id,
        "project_id": proj_id,
        "extraction_id": ext_id,
        "activity_index": 0,
        "recommended_activity_id": sched_act_id,
        "recommended_activity_code": "ACT-1001",
        "recommended_activity_name": "Erect Structural Steel Tier 1",
        "confidence_score": 0.94,
        "scoring_breakdown": match_rec.scoring_breakdown,
        "alternative_matches": [],
        "created_at": match_rec.created_at,
        "updated_at": match_rec.updated_at,
    }

    matching_service.repository = match_repo

    svc = DecisionService(
        decision_repo=decision_repo,
        actual_repo=actual_repo,
    )
    svc.match_repo = match_repo
    svc.schedule_service = schedule_svc
    svc.extraction_service = ext_svc

    return {
        "service": svc,
        "decision_repo": decision_repo,
        "actual_repo": actual_repo,
        "match_repo": match_repo,
        "project_id": proj_id,
        "planner_id": planner_id,
        "sched_act_id": sched_act_id,
        "alt_act_id": alt_act_id,
        "ext_id": ext_id,
        "match_id": match_id,
    }


@pytest.mark.asyncio
async def test_1_approve_creates_decision_and_approved_actual(decision_fixture):
    """Verify Approve creates an append-only decision audit record and official approved actual."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    actual = await svc.approve_match(
        project_id=proj_id,
        match_id=match_id,
        planner_id=planner_id,
        notes="Verified in morning inspection",
    )

    assert isinstance(actual, ApprovedActualResponse)
    assert actual.project_id == proj_id
    assert actual.approved_by == planner_id
    assert actual.actual_quantity == 10.0
    assert actual.actual_unit == "spools"
    assert actual.actual_date == date(2026, 8, 30)
    assert actual.is_modified is False
    assert actual.source_evidence == ["erected 10 spools", "Grid 4"]

    # Verify decision record
    dec = await svc.get_decision_for_match(proj_id, match_id)
    assert dec is not None
    assert dec.decision == PlannerDecisionType.APPROVED
    assert dec.decided_by == planner_id


@pytest.mark.asyncio
async def test_2_approve_preserves_original_ai_match(decision_fixture):
    """Verify Approve never mutates the original ai_matches record."""
    svc = decision_fixture["service"]
    match_repo = decision_fixture["match_repo"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    orig_match = await match_repo.get_match(proj_id, match_id)
    assert orig_match is not None

    await svc.approve_match(proj_id, match_id, planner_id)

    after_match = await match_repo.get_match(proj_id, match_id)
    assert after_match is not None
    assert orig_match.model_dump() == after_match.model_dump()


@pytest.mark.asyncio
async def test_3_approve_duplicate_is_idempotent(decision_fixture):
    """Verify duplicate approval calls return the same approved actual record without duplicates."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    actual_1 = await svc.approve_match(proj_id, match_id, planner_id)
    actual_2 = await svc.approve_match(proj_id, match_id, planner_id)

    assert actual_1.id == actual_2.id

    list_res = await svc.list_approved_actuals(proj_id)
    assert list_res.total == 1


@pytest.mark.asyncio
async def test_4_reject_creates_decision_and_no_approved_actual(decision_fixture):
    """Verify Reject creates a decision record with mandatory reason and NO approved actual."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    decision = await svc.reject_match(
        project_id=proj_id,
        match_id=match_id,
        planner_id=planner_id,
        rejection_reason="Duplicate field report entry",
    )

    assert decision.decision == PlannerDecisionType.REJECTED
    assert decision.rejection_reason == "Duplicate field report entry"
    assert decision.decided_by == planner_id

    # No approved actual created
    list_res = await svc.list_approved_actuals(proj_id)
    assert list_res.total == 0


@pytest.mark.asyncio
async def test_5_reject_requires_non_empty_reason(decision_fixture):
    """Verify rejection fails if rejection_reason is blank or whitespace."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    with pytest.raises(InvalidDecisionError):
        await svc.reject_match(proj_id, match_id, planner_id, "")

    with pytest.raises(InvalidDecisionError):
        await svc.reject_match(proj_id, match_id, planner_id, "   ")


@pytest.mark.asyncio
async def test_6_modify_creates_modified_decision_and_approved_actual(decision_fixture):
    """Verify Modify records original vs modified snapshot and creates approved actual with is_modified=True."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]
    alt_act_id = decision_fixture["alt_act_id"]

    mod_req = ModifyMatchRequest(
        schedule_activity_id=alt_act_id,
        actual_quantity=20.0,
        actual_unit="LF",
        actual_date=date(2026, 8, 30),
        notes="Corrected trade to underground piping",
    )

    actual = await svc.modify_match(
        project_id=proj_id,
        match_id=match_id,
        planner_id=planner_id,
        modification=mod_req,
    )

    assert actual.schedule_activity_id == alt_act_id
    assert actual.actual_quantity == 20.0
    assert actual.actual_unit == "LF"
    assert actual.is_modified is True
    assert actual.notes == "Corrected trade to underground piping"

    # Verify decision record
    dec = await svc.get_decision_for_match(proj_id, match_id)
    assert dec is not None
    assert dec.decision == PlannerDecisionType.MODIFIED
    assert dec.modified_payload is not None
    assert dec.modified_payload["actual_quantity"] == 20.0


@pytest.mark.asyncio
async def test_7_cross_project_match_rejected(decision_fixture):
    """Verify matching with foreign project ID raises CrossProjectDecisionError."""
    svc = decision_fixture["service"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]
    foreign_proj_id = uuid4()

    with pytest.raises((MatchNotFoundError, CrossProjectDecisionError)):
        await svc.approve_match(foreign_proj_id, match_id, planner_id)


@pytest.mark.asyncio
async def test_8_cross_project_schedule_activity_rejected_in_modify(decision_fixture):
    """Verify modifying to a schedule activity from another project is rejected."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]
    foreign_act_id = uuid4()

    # Seed foreign activity in different project
    svc.schedule_service._activities[str(foreign_act_id)] = {
        "id": str(foreign_act_id),
        "project_id": str(uuid4()),  # Different project
        "activity_code": "ACT-FOR",
        "name": "Foreign Activity",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mod_req = ModifyMatchRequest(
        schedule_activity_id=foreign_act_id,
        actual_date=date(2026, 8, 30),
    )

    with pytest.raises((ScheduleActivityNotFoundError, CrossProjectDecisionError)):
        await svc.modify_match(proj_id, match_id, planner_id, mod_req)


@pytest.mark.asyncio
async def test_9_re_decision_appends_new_audit_records(decision_fixture):
    """Verify rejection followed by approval appends two distinct decision records."""
    svc = decision_fixture["service"]
    decision_repo = decision_fixture["decision_repo"]
    proj_id = decision_fixture["project_id"]
    match_id = decision_fixture["match_id"]
    planner_id = decision_fixture["planner_id"]

    # 1. Reject first
    await svc.reject_match(proj_id, match_id, planner_id, "Need additional photo")

    # 2. Later Approve
    await svc.approve_match(proj_id, match_id, planner_id, "Photo confirmed work")

    decisions = await decision_repo.list_decisions(proj_id, match_id)
    assert len(decisions) == 2
    assert decisions[0].decision == PlannerDecisionType.APPROVED  # Latest first
    assert decisions[1].decision == PlannerDecisionType.REJECTED


@pytest.mark.asyncio
async def test_10_missing_match_rejected(decision_fixture):
    """Verify non-existent match ID raises MatchNotFoundError."""
    svc = decision_fixture["service"]
    proj_id = decision_fixture["project_id"]
    planner_id = decision_fixture["planner_id"]

    with pytest.raises(MatchNotFoundError):
        await svc.approve_match(proj_id, uuid4(), planner_id)
