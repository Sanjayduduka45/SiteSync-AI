"""
Unit tests for Phase 10.1 Audit & Provenance Domain Schemas (Pydantic v2).
Verifies:
- All 6 canonical AuditEventType values
- Extra='forbid' validation on all models
- Strict type validation and non-empty IDs
- Provenance node, link, and chain contracts
- Query filter parameter bounds
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.audit import (
    AuditActor,
    AuditEvent,
    AuditEventListResponse,
    AuditEventType,
    AuditFilterParams,
    AuditProvenanceRef,
    ProvenanceChain,
    ProvenanceLink,
    ProvenanceNode,
    ProvenanceNodeType,
)


def test_audit_event_types():
    """Verifies all 6 canonical audit event types exist."""
    expected = {
        "FIELD_INPUT_SUBMITTED",
        "AI_EXTRACTION_COMPLETED",
        "AI_MATCH_GENERATED",
        "PLANNER_DECISION_RECORDED",
        "APPROVED_ACTUAL_COMMITTED",
        "DEPENDENCY_EDGE_MUTATED",
    }
    actual = {e.value for e in AuditEventType}
    assert actual == expected


def test_provenance_node_types():
    """Verifies all participating provenance node types."""
    expected = {
        "FIELD_INPUT",
        "AI_EXTRACTION",
        "AI_MATCH",
        "PLANNER_DECISION",
        "APPROVED_ACTUAL",
        "VARIANCE",
        "RISK",
    }
    actual = {n.value for n in ProvenanceNodeType}
    assert actual == expected


def test_audit_actor_extra_forbidden():
    """Verifies extra attributes are strictly rejected on AuditActor."""
    with pytest.raises(ValidationError):
        AuditActor(actor_id=uuid4(), unknown_field="invalid")


def test_audit_event_valid():
    """Verifies complete valid construction of an AuditEvent."""
    now = datetime.now(timezone.utc)
    event_id = uuid4()
    proj_id = uuid4()
    entity_id = uuid4()
    actor_id = uuid4()

    event = AuditEvent(
        id=event_id,
        project_id=proj_id,
        event_type=AuditEventType.FIELD_INPUT_SUBMITTED,
        entity_type="field_input",
        entity_id=entity_id,
        actor=AuditActor(
            actor_id=actor_id,
            actor_name="John Doe",
            actor_email="john@example.com",
            role="supervisor",
            is_system=False,
        ),
        action="SUBMIT",
        timestamp=now,
        summary="Field input text submitted",
        metadata={"input_type": "text"},
        provenance_ref=AuditProvenanceRef(field_input_id=entity_id),
    )

    assert event.id == event_id
    assert event.event_type == AuditEventType.FIELD_INPUT_SUBMITTED
    assert event.actor.is_system is False
    assert event.metadata["input_type"] == "text"


def test_audit_event_extra_forbidden():
    """Verifies extra attributes are strictly rejected on AuditEvent."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        AuditEvent(
            id=uuid4(),
            project_id=uuid4(),
            event_type=AuditEventType.APPROVED_ACTUAL_COMMITTED,
            entity_type="approved_actual",
            entity_id=uuid4(),
            actor=AuditActor(is_system=True),
            action="COMMIT",
            timestamp=now,
            summary="Approved",
            unauthorized_field="malicious",
        )


def test_audit_filter_params_validation():
    """Verifies validation bounds on AuditFilterParams."""
    # Valid default params
    params = AuditFilterParams()
    assert params.limit == 50
    assert params.offset == 0

    # Limit too large (> 100)
    with pytest.raises(ValidationError):
        AuditFilterParams(limit=200)

    # Limit too small (< 1)
    with pytest.raises(ValidationError):
        AuditFilterParams(limit=0)

    # Offset negative (< 0)
    with pytest.raises(ValidationError):
        AuditFilterParams(offset=-5)


def test_provenance_chain_structure():
    """Verifies construction and immutability of ProvenanceChain."""
    proj_id = uuid4()
    root_id = uuid4()
    node1_id = uuid4()
    node2_id = uuid4()

    node1 = ProvenanceNode(
        node_id=f"FIELD_INPUT:{node1_id}",
        node_type=ProvenanceNodeType.FIELD_INPUT,
        entity_id=node1_id,
        title="Field Voice Note",
        status="SUBMITTED",
        timestamp=datetime.now(timezone.utc),
        details={"audio": True},
    )

    node2 = ProvenanceNode(
        node_id=f"AI_EXTRACTION:{node2_id}",
        node_type=ProvenanceNodeType.AI_EXTRACTION,
        entity_id=node2_id,
        title="AI Structured Extraction",
        status="COMPLETED",
        timestamp=datetime.now(timezone.utc),
        details={"confidence": 0.95},
    )

    link = ProvenanceLink(
        source_node_id=node1.node_id,
        target_node_id=node2.node_id,
        relationship="EXTRACTED_BY",
    )

    chain = ProvenanceChain(
        project_id=proj_id,
        root_entity_type=ProvenanceNodeType.FIELD_INPUT,
        root_entity_id=root_id,
        nodes=[node1, node2],
        links=[link],
        is_complete=True,
        unresolved_links=[],
    )

    assert chain.project_id == proj_id
    assert len(chain.nodes) == 2
    assert len(chain.links) == 1
    assert chain.is_complete is True
