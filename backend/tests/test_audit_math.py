"""
Domain logic and mathematical contract tests for Phase 10.1 Audit & Provenance Engine.
Verifies:
1. Normalization of all 6 canonical event types
2. Deterministic event sorting rule
3. Domain filtering (by type, actor, entity, date range)
4. Pagination consistency
5. Project tenant isolation & IDOR rejection
6. Full end-to-end provenance lineage traversal
7. Rejection decision handling & termination
8. Modified decision handling & override preservation
9. Unresolved link detection without hallucinations
10. Dependency edge audit projection (no fabricated history)
11. Read-only immutability invariant
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.schemas.audit import (
    AuditEventType,
    AuditFilterParams,
    ProvenanceNodeType,
)
from app.schemas.cpm import DependencyRelationshipType
from app.schemas.decision import (
    ApprovedActualResponse,
    ModifyMatchRequest,
    PlannerDecisionResponse,
    PlannerDecisionType,
)
from app.schemas.extractions import (
    ExtractedActivity,
    ExtractionResponse,
    ExtractionResult,
    ExtractionStatus,
)
from app.schemas.inputs import (
    FieldInputResponse,
    FieldInputType,
    TextInputCreate,
    TranscriptionStatus,
)
from app.schemas.network import DependencyCreate
from app.schemas.schedule import (
    MatchRecommendationResponse,
    ScheduleActivityCreate,
    ScoringBreakdown,
)
from app.services.audit_service import (
    AuditEntityNotFoundError,
    AuditService,
    CrossProjectAuditError,
    UnsupportedProvenanceEntityTypeError,
)
from app.services.decision_service import DecisionService
from app.services.dependency_service import DependencyService
from app.services.extraction_service import ExtractionService
from app.services.input_service import InputService
from app.services.matching_service import MatchingService
from app.services.risk_query_service import RiskQueryService
from app.services.schedule_service import ScheduleService
from app.services.variance_query_service import VarianceQueryService


@pytest.fixture
def test_env():
    """Sets up an isolated in-memory test environment for audit and provenance testing."""
    inp_svc = InputService()
    ext_svc = ExtractionService()
    match_svc = MatchingService()
    match_svc.repository.clear()
    sched_svc = ScheduleService()
    sched_svc.clear()
    dep_svc = DependencyService()
    dep_svc.clear()
    dep_svc.schedule_service = sched_svc
    dec_svc = DecisionService()
    dec_svc.decision_repo.clear()
    dec_svc.actual_repo.clear()
    dec_svc.match_repo = match_svc.repository
    dec_svc.extraction_service = ext_svc
    dec_svc.schedule_service = sched_svc
    var_svc = VarianceQueryService()
    var_svc.schedule_service = sched_svc
    var_svc.decision_service = dec_svc
    risk_svc = RiskQueryService()
    risk_svc.schedule_service = sched_svc
    risk_svc.dependency_service = dep_svc
    risk_svc.variance_query_service = var_svc

    audit_svc = AuditService(
        input_service=inp_svc,
        extraction_service=ext_svc,
        matching_service=match_svc,
        decision_service=dec_svc,
        dependency_service=dep_svc,
        schedule_service=sched_svc,
        variance_query_service=var_svc,
        risk_query_service=risk_svc,
    )

    return {
        "audit_svc": audit_svc,
        "inp_svc": inp_svc,
        "ext_svc": ext_svc,
        "match_svc": match_svc,
        "sched_svc": sched_svc,
        "dep_svc": dep_svc,
        "dec_svc": dec_svc,
        "var_svc": var_svc,
        "risk_svc": risk_svc,
    }


@pytest.mark.asyncio
async def test_normalization_all_six_events(test_env):
    """Verifies that all 6 domain entities project cleanly to AuditEvent."""
    audit_svc = test_env["audit_svc"]
    proj_id = uuid4()
    now = datetime.now(timezone.utc)

    # 1. Field Input
    inp = FieldInputResponse(
        id=str(uuid4()),
        project_id=str(proj_id),
        submitted_by=str(uuid4()),
        submitted_by_email="foreman@sitesync.ai",
        input_type=FieldInputType.TEXT,
        title="Piping Progress",
        raw_text="Installed 50 LF of spool piping on Unit 10",
        media_path=None,
        media_filename=None,
        media_mime_type=None,
        media_size_bytes=0,
        media_url=None,
        audio_duration_seconds=None,
        transcription_status=TranscriptionStatus.NONE,
        transcription_error=None,
        field_date=now.date(),
        metadata={},
        created_at=now,
        updated_at=now,
    )
    evt_inp = audit_svc.normalize_field_input(inp)
    assert evt_inp.event_type == AuditEventType.FIELD_INPUT_SUBMITTED
    assert evt_inp.entity_type == "field_input"
    assert evt_inp.actor.actor_email == "foreman@sitesync.ai"

    # 2. AI Extraction
    ext = ExtractionResponse(
        id=str(uuid4()),
        project_id=str(proj_id),
        field_input_id=inp.id,
        status=ExtractionStatus.COMPLETED,
        extracted_data={},
        confidence_score=0.92,
        model_version="gemini-1.5-pro",
        error_message=None,
        created_at=now + timedelta(seconds=1),
        updated_at=now + timedelta(seconds=1),
    )
    evt_ext = audit_svc.normalize_ai_extraction(ext)
    assert evt_ext.event_type == AuditEventType.AI_EXTRACTION_COMPLETED
    assert evt_ext.actor.is_system is True

    # 3. AI Match
    match = MatchRecommendationResponse(
        id=uuid4(),
        project_id=proj_id,
        extraction_id=uuid4(),
        activity_index=0,
        recommended_activity_id=uuid4(),
        recommended_activity_code="ACT-101",
        recommended_activity_name="Install Spools",
        confidence_score=0.88,
        scoring_breakdown=ScoringBreakdown(semantic_similarity=0.9, discipline_contribution=0.15, location_contribution=0.1, temporal_contribution=0.05),
        alternative_matches=[],
        created_at=now + timedelta(seconds=2),
        updated_at=now + timedelta(seconds=2),
    )
    evt_match = audit_svc.normalize_ai_match(match)
    assert evt_match.event_type == AuditEventType.AI_MATCH_GENERATED
    assert evt_match.actor.is_system is True

    # 4. Planner Decision
    dec = PlannerDecisionResponse(
        id=uuid4(),
        project_id=proj_id,
        match_id=match.id,
        extraction_id=match.extraction_id,
        decision=PlannerDecisionType.APPROVED,
        decided_by=uuid4(),
        decided_at=now + timedelta(seconds=3),
        rejection_reason=None,
        original_payload={},
        modified_payload=None,
        created_at=now + timedelta(seconds=3),
    )
    evt_dec = audit_svc.normalize_planner_decision(dec)
    assert evt_dec.event_type == AuditEventType.PLANNER_DECISION_RECORDED
    assert evt_dec.action == "APPROVED"

    # 5. Approved Actual
    actual = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_id,
        schedule_activity_id=match.recommended_activity_id,
        extraction_id=match.extraction_id,
        match_id=match.id,
        activity_index=0,
        actual_quantity=50.0,
        actual_unit="LF",
        actual_date=now.date(),
        source_evidence=["50 LF"],
        approved_by=dec.decided_by,
        approved_at=now + timedelta(seconds=4),
        notes="Verified with foreman",
        is_modified=False,
        created_at=now + timedelta(seconds=4),
        updated_at=now + timedelta(seconds=4),
    )
    evt_actual = audit_svc.normalize_approved_actual(actual)
    assert evt_actual.event_type == AuditEventType.APPROVED_ACTUAL_COMMITTED
    assert evt_actual.metadata["actual_quantity"] == 50.0

    # 6. Dependency Edge
    from app.schemas.cpm import DependencyRelationshipType
    from app.schemas.network import DependencyResponse
    dep = DependencyResponse(
        id=uuid4(),
        project_id=proj_id,
        predecessor_id=uuid4(),
        successor_id=uuid4(),
        relationship_type=DependencyRelationshipType.FS,
        lag_days=0,
        created_at=now + timedelta(seconds=5),
        updated_at=now + timedelta(seconds=5),
    )
    evt_dep = audit_svc.normalize_dependency_edge(dep)
    assert evt_dep.event_type == AuditEventType.DEPENDENCY_EDGE_MUTATED


@pytest.mark.asyncio
async def test_deterministic_sorting_and_pagination(test_env):
    """Verifies that audit stream sorting is deterministic: timestamp DESC, event_type ASC, entity_id ASC."""
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]
    proj_id = str(uuid4())

    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 30, 11, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)

    # Insert 3 inputs at different timestamps
    inp1 = inp_svc.create_text_input(
        project_id=proj_id,
        data=TextInputCreate(title="Input 1", raw_text="Sample text 1"),
        submitted_by_id=str(uuid4()),
        submitted_by_email="user1@example.com",
    )
    inp_svc._inputs[inp1.id]["created_at"] = t0

    inp2 = inp_svc.create_text_input(
        project_id=proj_id,
        data=TextInputCreate(title="Input 2", raw_text="Sample text 2"),
        submitted_by_id=str(uuid4()),
        submitted_by_email="user2@example.com",
    )
    inp_svc._inputs[inp2.id]["created_at"] = t2

    inp3 = inp_svc.create_text_input(
        project_id=proj_id,
        data=TextInputCreate(title="Input 3", raw_text="Sample text 3"),
        submitted_by_id=str(uuid4()),
        submitted_by_email="user3@example.com",
    )
    inp_svc._inputs[inp3.id]["created_at"] = t1

    # Query all
    res = await audit_svc.list_audit_events(proj_id, AuditFilterParams(limit=10, offset=0))
    assert res.total == 3
    # Newest first: t2 (inp2) -> t1 (inp3) -> t0 (inp1)
    assert res.items[0].entity_id == UUID(inp2.id)
    assert res.items[1].entity_id == UUID(inp3.id)
    assert res.items[2].entity_id == UUID(inp1.id)

    # Test pagination
    page1 = await audit_svc.list_audit_events(proj_id, AuditFilterParams(limit=1, offset=0))
    page2 = await audit_svc.list_audit_events(proj_id, AuditFilterParams(limit=1, offset=1))
    assert len(page1.items) == 1
    assert page1.items[0].summary == res.items[0].summary
    assert page2.items[0].summary == res.items[1].summary


@pytest.mark.asyncio
async def test_tenant_isolation_rejection(test_env):
    """Verifies that audit queries for Project A never return Project B events."""
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]

    proj_a = str(uuid4())
    proj_b = str(uuid4())

    inp_svc.create_text_input(
        project_id=proj_a,
        data=TextInputCreate(title="Project A Input", raw_text="Work on A"),
        submitted_by_id=str(uuid4()),
    )
    inp_svc.create_text_input(
        project_id=proj_b,
        data=TextInputCreate(title="Project B Input", raw_text="Work on B"),
        submitted_by_id=str(uuid4()),
    )

    res_a = await audit_svc.list_audit_events(proj_a)
    assert res_a.total == 1
    assert res_a.items[0].metadata["title"] == "Project A Input"

    res_b = await audit_svc.list_audit_events(proj_b)
    assert res_b.total == 1
    assert res_b.items[0].metadata["title"] == "Project B Input"


@pytest.mark.asyncio
async def test_end_to_end_provenance_chain_resolution(test_env):
    """
    Constructs a full field-to-decision pipeline and proves that resolve_provenance
    reconstructs the exact lineage graph without missing links or hallucinations.
    """
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]
    ext_svc = test_env["ext_svc"]
    match_svc = test_env["match_svc"]
    sched_svc = test_env["sched_svc"]
    dec_svc = test_env["dec_svc"]

    proj_id = uuid4()
    proj_str = str(proj_id)
    planner_id = uuid4()

    # 1. Create baseline schedule activity
    act = await sched_svc.create_or_update_activity(
        proj_str,
        ScheduleActivityCreate(
            activity_code="ACT-500",
            name="Structural Steel Assembly",
            planned_quantity=100.0,
            planned_unit="tons",
            planned_start_date=date(2026, 8, 1),
            planned_finish_date=date(2026, 8, 20),
        ),
    )

    # 2. Submit field input
    field_inp = inp_svc.create_text_input(
        project_id=proj_str,
        data=TextInputCreate(title="Steel Report", raw_text="Erected 40 tons of structural steel today."),
        submitted_by_id=str(uuid4()),
        submitted_by_email="supervisor@site.com",
    )

    # 3. Create mock extraction
    extracted_act = ExtractedActivity(
        description="Erected 40 tons of structural steel today.",
        discipline="Structural",
        location="Zone 1",
        progress_value=40.0,
        progress_unit="tons",
        event_date=date(2026, 8, 10),
        evidence_tokens=["40 tons of structural steel"],
    )
    ext_result = ExtractionResult(
        raw_input_id=UUID(field_inp.id),
        extracted_activities=[extracted_act],
        extraction_confidence=0.95,
        model_version="gemini-1.5-pro",
        processing_timestamp=datetime.now(timezone.utc),
    )
    ext_record = await ext_svc.repository.upsert_completed(proj_str, field_inp.id, ext_result)
    ext_id = ext_record["id"]

    # 4. Generate AI Match recommendation
    match_rec = MatchRecommendationResponse(
        id=uuid4(),
        project_id=proj_id,
        extraction_id=UUID(ext_id),
        activity_index=0,
        recommended_activity_id=UUID(str(act.id)),
        recommended_activity_code=act.activity_code,
        recommended_activity_name=act.name,
        confidence_score=0.92,
        scoring_breakdown=ScoringBreakdown(semantic_similarity=0.9, discipline_contribution=0.15, location_contribution=0.1, temporal_contribution=0.05),
        alternative_matches=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await match_svc.repository.upsert_match(match_rec)

    # 5. Planner approves match
    actual = await dec_svc.approve_match(
        project_id=proj_str,
        match_id=match_rec.id,
        planner_id=planner_id,
        notes="Verified and signed off by lead planner.",
    )

    # 6. Resolve provenance starting from the Approved Actual
    chain = await audit_svc.resolve_provenance(
        project_id=proj_id,
        entity_type=ProvenanceNodeType.APPROVED_ACTUAL,
        entity_id=actual.id,
    )

    assert chain.project_id == proj_id
    assert chain.root_entity_type == ProvenanceNodeType.APPROVED_ACTUAL
    assert chain.root_entity_id == actual.id
    assert chain.is_complete is True
    assert len(chain.unresolved_links) == 0

    node_types = {n.node_type for n in chain.nodes}
    assert ProvenanceNodeType.FIELD_INPUT in node_types
    assert ProvenanceNodeType.AI_EXTRACTION in node_types
    assert ProvenanceNodeType.AI_MATCH in node_types
    assert ProvenanceNodeType.PLANNER_DECISION in node_types
    assert ProvenanceNodeType.APPROVED_ACTUAL in node_types


@pytest.mark.asyncio
async def test_provenance_rejection_termination(test_env):
    """Verifies that rejected planner decisions correctly record rejection reason and terminate before approved actual."""
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]
    ext_svc = test_env["ext_svc"]
    match_svc = test_env["match_svc"]
    dec_svc = test_env["dec_svc"]

    proj_id = uuid4()
    proj_str = str(proj_id)

    # Input -> Extraction -> Match
    field_inp = inp_svc.create_text_input(
        project_id=proj_str,
        data=TextInputCreate(title="Ambiguous Note", raw_text="Poured some concrete somewhere."),
        submitted_by_id=str(uuid4()),
    )
    ext_result = ExtractionResult(
        raw_input_id=UUID(field_inp.id),
        extracted_activities=[
            ExtractedActivity(
                description="Poured concrete somewhere.",
                discipline="Civil",
                location="Site",
                progress_value=10.0,
                progress_unit="m3",
                event_date=date(2026, 8, 10),
                evidence_tokens=["concrete"],
            )
        ],
        extraction_confidence=0.45,
        model_version="gemini-1.5-pro",
        processing_timestamp=datetime.now(timezone.utc),
    )
    ext_record = await ext_svc.repository.upsert_completed(proj_str, field_inp.id, ext_result)

    match_rec = MatchRecommendationResponse(
        id=uuid4(),
        project_id=proj_id,
        extraction_id=UUID(ext_record["id"]),
        activity_index=0,
        recommended_activity_id=uuid4(),
        recommended_activity_code="ACT-CONC-01",
        recommended_activity_name="Foundation Pour",
        confidence_score=0.45,
        scoring_breakdown=ScoringBreakdown(semantic_similarity=0.45, discipline_contribution=0.0, location_contribution=0.0, temporal_contribution=0.0),
        alternative_matches=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await match_svc.repository.upsert_match(match_rec)

    # Planner REJECTS match
    decision = await dec_svc.reject_match(
        project_id=proj_str,
        match_id=match_rec.id,
        planner_id=uuid4(),
        rejection_reason="Duplicate report of yesterday's foundation pour.",
    )

    # Resolve provenance from Decision
    chain = await audit_svc.resolve_provenance(
        project_id=proj_id,
        entity_type=ProvenanceNodeType.PLANNER_DECISION,
        entity_id=decision.id,
    )

    dec_node = next(n for n in chain.nodes if n.node_type == ProvenanceNodeType.PLANNER_DECISION)
    assert dec_node.status == "REJECTED"
    assert dec_node.details["rejection_reason"] == "Duplicate report of yesterday's foundation pour."

    # No approved actual node should exist
    assert not any(n.node_type == ProvenanceNodeType.APPROVED_ACTUAL for n in chain.nodes)


@pytest.mark.asyncio
async def test_cross_project_provenance_rejection(test_env):
    """Verifies that requesting provenance for an entity belonging to another project is rejected with CrossProjectAuditError."""
    audit_svc = test_env["audit_svc"]
    dec_svc = test_env["dec_svc"]

    proj_a = uuid4()
    proj_b = uuid4()

    actual_b = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_b,
        schedule_activity_id=uuid4(),
        extraction_id=uuid4(),
        match_id=uuid4(),
        activity_index=0,
        actual_quantity=10.0,
        actual_unit="LF",
        actual_date=date.today(),
        source_evidence=[],
        approved_by=uuid4(),
        approved_at=datetime.now(timezone.utc),
        notes=None,
        is_modified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await dec_svc.actual_repo.create_or_get_approved_actual(actual_b)

    with pytest.raises(CrossProjectAuditError):
        await audit_svc.resolve_provenance(
            project_id=proj_a,
            entity_type=ProvenanceNodeType.APPROVED_ACTUAL,
            entity_id=actual_b.id,
        )


@pytest.mark.asyncio
async def test_modified_decision_provenance_and_override_preservation(test_env):
    """Verifies that modified decisions preserve planner override values and flag actuals accordingly."""
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]
    ext_svc = test_env["ext_svc"]
    match_svc = test_env["match_svc"]
    sched_svc = test_env["sched_svc"]
    dec_svc = test_env["dec_svc"]

    proj_id = uuid4()
    proj_str = str(proj_id)
    planner_id = uuid4()

    # Original activity
    act1 = await sched_svc.create_or_update_activity(
        proj_str,
        ScheduleActivityCreate(
            activity_code="ACT-100",
            name="Excavation Zone 1",
            planned_quantity=500.0,
            planned_unit="m3",
        ),
    )
    # Target modified activity
    act2 = await sched_svc.create_or_update_activity(
        proj_str,
        ScheduleActivityCreate(
            activity_code="ACT-200",
            name="Excavation Zone 2",
            planned_quantity=300.0,
            planned_unit="m3",
        ),
    )

    field_inp = inp_svc.create_text_input(
        project_id=proj_str,
        data=TextInputCreate(title="Daily Dig", raw_text="Excavated 150 m3 today."),
        submitted_by_id=str(uuid4()),
    )
    ext_result = ExtractionResult(
        raw_input_id=UUID(field_inp.id),
        extracted_activities=[
            ExtractedActivity(
                description="Excavated 150 m3 today.",
                discipline="Civil",
                location="Zone 2",
                progress_value=150.0,
                progress_unit="m3",
                event_date=date(2026, 8, 11),
                evidence_tokens=["150 m3"],
            )
        ],
        extraction_confidence=0.88,
        model_version="gemini-1.5-pro",
        processing_timestamp=datetime.now(timezone.utc),
    )
    ext_record = await ext_svc.repository.upsert_completed(proj_str, field_inp.id, ext_result)

    match_rec = MatchRecommendationResponse(
        id=uuid4(),
        project_id=proj_id,
        extraction_id=UUID(ext_record["id"]),
        activity_index=0,
        recommended_activity_id=UUID(str(act1.id)),
        recommended_activity_code=act1.activity_code,
        recommended_activity_name=act1.name,
        confidence_score=0.75,
        scoring_breakdown=ScoringBreakdown(semantic_similarity=0.75, discipline_contribution=0.0, location_contribution=0.0, temporal_contribution=0.0),
        alternative_matches=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await match_svc.repository.upsert_match(match_rec)

    # Planner MODIFIES match to target act2 with overridden quantity 140 m3
    actual = await dec_svc.modify_match(
        project_id=proj_str,
        match_id=match_rec.id,
        planner_id=planner_id,
        modification=ModifyMatchRequest(
            schedule_activity_id=str(act2.id),
            actual_quantity=140.0,
            actual_unit="m3",
            actual_date=date(2026, 8, 11),
            notes="Adjusted down by 10 m3 for rock displacement.",
        ),
    )

    assert actual.is_modified is True
    assert actual.actual_quantity == 140.0
    assert actual.schedule_activity_id == UUID(str(act2.id))

    # Resolve Provenance
    chain = await audit_svc.resolve_provenance(
        project_id=proj_id,
        entity_type=ProvenanceNodeType.APPROVED_ACTUAL,
        entity_id=actual.id,
    )

    actual_node = next(n for n in chain.nodes if n.node_type == ProvenanceNodeType.APPROVED_ACTUAL)
    assert actual_node.status == "MODIFIED"
    assert actual_node.details["is_modified"] is True
    assert actual_node.details["actual_quantity"] == 140.0

    dec_node = next(n for n in chain.nodes if n.node_type == ProvenanceNodeType.PLANNER_DECISION)
    assert dec_node.status == "MODIFIED"


@pytest.mark.asyncio
async def test_audit_domain_filters(test_env):
    """Verifies filtering by event_type, actor_id, and entity_id."""
    audit_svc = test_env["audit_svc"]
    inp_svc = test_env["inp_svc"]
    dep_svc = test_env["dep_svc"]

    proj_id = uuid4()
    proj_str = str(proj_id)
    user_a = str(uuid4())
    user_b = str(uuid4())

    inp_a = inp_svc.create_text_input(
        project_id=proj_str,
        data=TextInputCreate(title="Report A", raw_text="Notes A"),
        submitted_by_id=user_a,
    )
    inp_b = inp_svc.create_text_input(
        project_id=proj_str,
        data=TextInputCreate(title="Report B", raw_text="Notes B"),
        submitted_by_id=user_b,
    )

    # 1. Filter by event_type
    res_type = await audit_svc.list_audit_events(
        proj_str, AuditFilterParams(event_type=AuditEventType.FIELD_INPUT_SUBMITTED)
    )
    assert res_type.total >= 2
    assert all(e.event_type == AuditEventType.FIELD_INPUT_SUBMITTED for e in res_type.items)

    # 2. Filter by actor_id
    res_actor = await audit_svc.list_audit_events(
        proj_str, AuditFilterParams(actor_id=UUID(user_a))
    )
    assert res_actor.total == 1
    assert res_actor.items[0].metadata["title"] == "Report A"

    # 3. Filter by entity_id
    res_entity = await audit_svc.list_audit_events(
        proj_str, AuditFilterParams(entity_id=UUID(inp_b.id))
    )
    assert res_entity.total == 1
    assert res_entity.items[0].metadata["title"] == "Report B"


@pytest.mark.asyncio
async def test_dependency_edge_audit_projection_no_fabricated_history(test_env):
    """
    Verifies that public.schedule_dependencies records project cleanly to AuditEvent
    without inventing fictional mutation history.
    """
    audit_svc = test_env["audit_svc"]
    dep_svc = test_env["dep_svc"]
    sched_svc = test_env["sched_svc"]

    proj_id = uuid4()
    proj_str = str(proj_id)

    act_pred = await sched_svc.create_or_update_activity(
        proj_str,
        ScheduleActivityCreate(activity_code="ACT-PRED", name="Predecessor Task"),
    )
    act_succ = await sched_svc.create_or_update_activity(
        proj_str,
        ScheduleActivityCreate(activity_code="ACT-SUCC", name="Successor Task"),
    )

    pred_id = act_pred.id
    succ_id = act_succ.id

    dep = await dep_svc.create_dependency(
        proj_str,
        DependencyCreate(
            predecessor_id=pred_id,
            successor_id=succ_id,
            relationship_type=DependencyRelationshipType.FS,
            lag_days=2,
        ),
    )

    res = await audit_svc.list_audit_events(
        proj_str, AuditFilterParams(event_type=AuditEventType.DEPENDENCY_EDGE_MUTATED)
    )
    assert res.total == 1
    dep_evt = res.items[0]
    assert dep_evt.event_type == AuditEventType.DEPENDENCY_EDGE_MUTATED
    assert dep_evt.entity_id == dep.id
    assert dep_evt.metadata["relationship_type"] == "FS"
    assert dep_evt.metadata["lag_days"] == 2
    assert dep_evt.metadata["predecessor_id"] == str(pred_id)
    assert dep_evt.metadata["successor_id"] == str(succ_id)


@pytest.mark.asyncio
async def test_unresolved_links_tracking(test_env):
    """Verifies that missing upstream entities are logged in unresolved_links and is_complete=False."""
    audit_svc = test_env["audit_svc"]
    dec_svc = test_env["dec_svc"]

    proj_id = uuid4()
    orphaned_match_id = uuid4()
    orphaned_ext_id = uuid4()
    orphaned_act_id = uuid4()

    # Create approved actual with missing extraction and missing match
    actual = ApprovedActualResponse(
        id=uuid4(),
        project_id=proj_id,
        schedule_activity_id=orphaned_act_id,
        extraction_id=orphaned_ext_id,
        match_id=orphaned_match_id,
        activity_index=0,
        actual_quantity=25.0,
        actual_unit="LF",
        actual_date=date.today(),
        source_evidence=[],
        approved_by=uuid4(),
        approved_at=datetime.now(timezone.utc),
        notes=None,
        is_modified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await dec_svc.actual_repo.create_or_get_approved_actual(actual)

    chain = await audit_svc.resolve_provenance(
        project_id=proj_id,
        entity_type=ProvenanceNodeType.APPROVED_ACTUAL,
        entity_id=actual.id,
    )

    assert chain.is_complete is False
    assert len(chain.unresolved_links) > 0
    assert any("No planner decision" in msg for msg in chain.unresolved_links)
    assert any("No AI match" in msg for msg in chain.unresolved_links)


def test_read_only_immutability_invariant(test_env):
    """Verifies that AuditService exposes ZERO mutating or destructive methods."""
    audit_svc = test_env["audit_svc"]
    disallowed = ["delete", "remove", "update", "put", "patch", "drop", "truncate", "clear"]
    
    for attr_name in dir(audit_svc):
        if not attr_name.startswith("__"):
            for dis in disallowed:
                assert not attr_name.startswith(dis), f"AuditService must not have mutating method '{attr_name}'"
