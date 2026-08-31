"""
SiteSync AI — Phase 10.1 Audit & Provenance Domain Schemas.
Pydantic v2 models defining the canonical 6-event audit taxonomy,
provenance graph nodes, links, and query filter parameters (ADR-019, ADR-020, ADR-021).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(str, Enum):
    """Canonical 6-event lifecycle taxonomy defined in ADR-020."""
    FIELD_INPUT_SUBMITTED = "FIELD_INPUT_SUBMITTED"
    AI_EXTRACTION_COMPLETED = "AI_EXTRACTION_COMPLETED"
    AI_MATCH_GENERATED = "AI_MATCH_GENERATED"
    PLANNER_DECISION_RECORDED = "PLANNER_DECISION_RECORDED"
    APPROVED_ACTUAL_COMMITTED = "APPROVED_ACTUAL_COMMITTED"
    DEPENDENCY_EDGE_MUTATED = "DEPENDENCY_EDGE_MUTATED"


class AuditAction(str, Enum):
    """Action classifier for audit events."""
    SUBMIT = "SUBMIT"
    EXTRACT = "EXTRACT"
    RECOMMEND = "RECOMMEND"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    COMMIT_ACTUAL = "COMMIT_ACTUAL"
    ESTABLISH_EDGE = "ESTABLISH_EDGE"
    DELETE_EDGE = "DELETE_EDGE"


class ProvenanceNodeType(str, Enum):
    """Entity types participating in the field-to-schedule provenance lineage."""
    FIELD_INPUT = "FIELD_INPUT"
    AI_EXTRACTION = "AI_EXTRACTION"
    AI_MATCH = "AI_MATCH"
    PLANNER_DECISION = "PLANNER_DECISION"
    APPROVED_ACTUAL = "APPROVED_ACTUAL"
    VARIANCE = "VARIANCE"
    RISK = "RISK"


class AuditActor(BaseModel):
    """Identity and role of the actor executing or initiating an event."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: Optional[UUID] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    role: Optional[str] = None
    is_system: bool = False


class AuditProvenanceRef(BaseModel):
    """Direct foreign identifiers for tracing lineage across domain entities."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_input_id: Optional[UUID] = None
    extraction_id: Optional[UUID] = None
    match_id: Optional[UUID] = None
    decision_id: Optional[UUID] = None
    approved_actual_id: Optional[UUID] = None
    schedule_activity_id: Optional[UUID] = None


class AuditEvent(BaseModel):
    """
    Normalized, immutable representation of a domain lifecycle event.
    Constructed deterministically from underlying append-only source records.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    event_type: AuditEventType
    entity_type: str
    entity_id: UUID
    actor: AuditActor
    action: str
    timestamp: datetime
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance_ref: AuditProvenanceRef = Field(default_factory=AuditProvenanceRef)


class AuditFilterParams(BaseModel):
    """Query filter parameters for the audit log stream."""
    model_config = ConfigDict(extra="forbid")

    event_type: Optional[AuditEventType] = None
    actor_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AuditEventListResponse(BaseModel):
    """Paginated response containing normalized audit events."""
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEvent]
    total: int
    limit: int
    offset: int


# ==============================================================================
# Provenance Lineage Graph Models
# ==============================================================================

class ProvenanceNode(BaseModel):
    """A single stage or entity node in the provenance chain."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    node_type: ProvenanceNodeType
    entity_id: UUID
    title: str
    status: Optional[str] = None
    timestamp: Optional[datetime] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProvenanceLink(BaseModel):
    """Directed causal relationship connecting two provenance nodes."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_node_id: str
    target_node_id: str
    relationship: str


class ProvenanceChain(BaseModel):
    """
    Full upstream and downstream provenance lineage graph for an entity.
    Traces Field Input -> Extraction -> Match -> Decision -> Actual -> Variance/Risk.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    root_entity_type: ProvenanceNodeType
    root_entity_id: UUID
    nodes: list[ProvenanceNode]
    links: list[ProvenanceLink]
    is_complete: bool
    unresolved_links: list[str] = Field(default_factory=list)
