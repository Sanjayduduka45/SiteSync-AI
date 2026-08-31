"""
SiteSync AI — Phase 10.1 Audit & Provenance Domain Query Engine.
Provides deterministic read-only projection of domain records into canonical audit events,
and resolves end-to-end provenance graphs across the field-to-schedule lifecycle (ADR-019, ADR-020, ADR-021).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from app.schemas.audit import (
    AuditAction,
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
from app.schemas.decision import (
    ApprovedActualResponse,
    PlannerDecisionResponse,
    PlannerDecisionType,
)
from app.schemas.extractions import ExtractionResponse, ExtractionStatus
from app.schemas.inputs import FieldInputResponse
from app.schemas.network import DependencyResponse
from app.schemas.schedule import MatchRecommendationResponse
from app.services.decision_service import DecisionService
from app.services.dependency_service import DependencyService
from app.services.extraction_service import ExtractionService
from app.services.input_service import InputService
from app.services.matching_service import MatchingService
from app.services.risk_query_service import RiskQueryService
from app.services.schedule_service import ScheduleService
from app.services.variance_query_service import VarianceQueryService

logger = logging.getLogger(__name__)


def _parse_uuid(val: Any) -> UUID:
    """Safely converts string or UUID to UUID object, resolving non-hex strings deterministically."""
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return uuid5(NAMESPACE_DNS, str(val))


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class AuditError(Exception):
    """Base domain exception for audit and provenance operations."""


class CrossProjectAuditError(AuditError):
    """Raised when an entity does not belong to the requested project scope."""


class AuditEntityNotFoundError(AuditError):
    """Raised when a requested root entity for provenance resolution is not found."""


class UnsupportedProvenanceEntityTypeError(AuditError):
    """Raised when an unrecognized entity type is requested for provenance resolution."""


# ==============================================================================
# AuditService Domain Engine
# ==============================================================================

class AuditService:
    """
    Pure domain query service for audit log normalization and provenance resolution.
    Strictly read-only; performs zero mutations on underlying tables.
    """

    def __init__(
        self,
        input_service: Optional[InputService] = None,
        extraction_service: Optional[ExtractionService] = None,
        matching_service: Optional[MatchingService] = None,
        decision_service: Optional[DecisionService] = None,
        dependency_service: Optional[DependencyService] = None,
        schedule_service: Optional[ScheduleService] = None,
        variance_query_service: Optional[VarianceQueryService] = None,
        risk_query_service: Optional[RiskQueryService] = None,
    ) -> None:
        from app.services.decision_service import (
            DecisionService,
            decision_service as dec_inst,
        )
        from app.services.dependency_service import dependency_service as dep_inst
        from app.services.extraction_service import extraction_service as ext_inst
        from app.services.input_service import input_service as inp_inst
        from app.services.matching_service import matching_service as match_inst
        from app.services.risk_query_service import risk_query_service as risk_inst
        from app.services.schedule_service import schedule_service as sched_inst
        from app.services.variance_query_service import variance_query_service as var_inst

        self.input_service = input_service or inp_inst
        self.extraction_service = extraction_service or ext_inst
        self.matching_service = matching_service or match_inst
        self.decision_service = decision_service or dec_inst
        self.dependency_service = dependency_service or dep_inst
        self.schedule_service = schedule_service or sched_inst
        self.variance_query_service = variance_query_service or var_inst
        self.risk_query_service = risk_query_service or risk_inst

    # ==========================================================================
    # 1. Normalization Projections
    # ==========================================================================

    def normalize_field_input(self, inp: FieldInputResponse) -> AuditEvent:
        """Projects a raw FieldInput record into an AuditEvent."""
        proj_uuid = _parse_uuid(inp.project_id)
        inp_uuid = _parse_uuid(inp.id)
        actor_uuid = _parse_uuid(inp.submitted_by) if inp.submitted_by else None

        actor = AuditActor(
            actor_id=actor_uuid,
            actor_name=None,
            actor_email=inp.submitted_by_email,
            role="supervisor",
            is_system=False,
        )
        provenance = AuditProvenanceRef(field_input_id=inp_uuid)
        metadata = {
            "input_type": inp.input_type.value,
            "title": inp.title,
            "media_mime_type": inp.media_mime_type,
            "transcription_status": inp.transcription_status.value,
            "field_date": inp.field_date.isoformat(),
        }

        # Deterministic synthetic event ID derived from entity ID and timestamp
        event_id = uuid5(inp_uuid, f"FIELD_INPUT_SUBMITTED:{inp.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.FIELD_INPUT_SUBMITTED,
            entity_type="field_input",
            entity_id=inp_uuid,
            actor=actor,
            action="SUBMIT",
            timestamp=inp.created_at,
            summary=f"Field input ({inp.input_type.value}) submitted by {inp.submitted_by_email or inp.submitted_by}",
            metadata=metadata,
            provenance_ref=provenance,
        )

    def normalize_ai_extraction(self, ext: ExtractionResponse) -> AuditEvent:
        """Projects an AIExtraction record into an AuditEvent."""
        proj_uuid = _parse_uuid(ext.project_id)
        ext_uuid = _parse_uuid(ext.id)
        inp_uuid = _parse_uuid(ext.field_input_id)

        actor = AuditActor(
            actor_id=None,
            actor_name=ext.model_version,
            actor_email=None,
            role="AI_SYSTEM",
            is_system=True,
        )
        provenance = AuditProvenanceRef(
            field_input_id=inp_uuid,
            extraction_id=ext_uuid,
        )
        metadata = {
            "status": ext.status.value,
            "confidence_score": ext.confidence_score,
            "model_version": ext.model_version,
            "error_message": ext.error_message,
        }

        event_id = uuid5(ext_uuid, f"AI_EXTRACTION_COMPLETED:{ext.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.AI_EXTRACTION_COMPLETED,
            entity_type="ai_extraction",
            entity_id=ext_uuid,
            actor=actor,
            action="EXTRACT",
            timestamp=ext.created_at,
            summary=f"AI extraction completed with status '{ext.status.value}' (confidence: {ext.confidence_score})",
            metadata=metadata,
            provenance_ref=provenance,
        )

    def normalize_ai_match(self, match: MatchRecommendationResponse) -> AuditEvent:
        """Projects an AIMatch record into an AuditEvent."""
        proj_uuid = _parse_uuid(match.project_id)
        match_uuid = _parse_uuid(match.id)
        ext_uuid = _parse_uuid(match.extraction_id)
        sched_uuid = _parse_uuid(match.recommended_activity_id)

        actor = AuditActor(
            actor_id=None,
            actor_name="MatchEngine",
            actor_email=None,
            role="AI_SYSTEM",
            is_system=True,
        )
        provenance = AuditProvenanceRef(
            extraction_id=ext_uuid,
            match_id=match_uuid,
            schedule_activity_id=sched_uuid,
        )
        metadata = {
            "activity_index": match.activity_index,
            "recommended_activity_code": match.recommended_activity_code,
            "recommended_activity_name": match.recommended_activity_name,
            "confidence_score": match.confidence_score,
            "scoring_breakdown": match.scoring_breakdown.model_dump(),
        }

        event_id = uuid5(match_uuid, f"AI_MATCH_GENERATED:{match.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.AI_MATCH_GENERATED,
            entity_type="ai_match",
            entity_id=match_uuid,
            actor=actor,
            action="RECOMMEND",
            timestamp=match.created_at,
            summary=f"AI match recommended activity '{match.recommended_activity_code or sched_uuid}' (score: {match.confidence_score})",
            metadata=metadata,
            provenance_ref=provenance,
        )

    def normalize_planner_decision(self, dec: PlannerDecisionResponse) -> AuditEvent:
        """Projects a PlannerDecision record into an AuditEvent."""
        proj_uuid = _parse_uuid(dec.project_id)
        dec_uuid = _parse_uuid(dec.id)
        match_uuid = _parse_uuid(dec.match_id)
        ext_uuid = _parse_uuid(dec.extraction_id)
        planner_uuid = _parse_uuid(dec.decided_by)

        actor = AuditActor(
            actor_id=planner_uuid,
            actor_name=None,
            actor_email=None,
            role="planner",
            is_system=False,
        )
        provenance = AuditProvenanceRef(
            extraction_id=ext_uuid,
            match_id=match_uuid,
            decision_id=dec_uuid,
        )
        metadata = {
            "decision": dec.decision.value,
            "rejection_reason": dec.rejection_reason,
            "is_modified": dec.decision == PlannerDecisionType.MODIFIED,
            "has_overrides": dec.modified_payload is not None,
        }

        event_id = uuid5(dec_uuid, f"PLANNER_DECISION_RECORDED:{dec.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.PLANNER_DECISION_RECORDED,
            entity_type="planner_decision",
            entity_id=dec_uuid,
            actor=actor,
            action=dec.decision.value.upper(),
            timestamp=dec.decided_at or dec.created_at,
            summary=f"Planner recorded decision '{dec.decision.value}' on match recommendation",
            metadata=metadata,
            provenance_ref=provenance,
        )

    def normalize_approved_actual(self, actual: ApprovedActualResponse) -> AuditEvent:
        """Projects an ApprovedActual record into an AuditEvent."""
        proj_uuid = _parse_uuid(actual.project_id)
        actual_uuid = _parse_uuid(actual.id)
        sched_uuid = _parse_uuid(actual.schedule_activity_id)
        ext_uuid = _parse_uuid(actual.extraction_id)
        match_uuid = _parse_uuid(actual.match_id)
        approver_uuid = _parse_uuid(actual.approved_by)

        actor = AuditActor(
            actor_id=approver_uuid,
            actor_name=None,
            actor_email=None,
            role="planner",
            is_system=False,
        )
        provenance = AuditProvenanceRef(
            extraction_id=ext_uuid,
            match_id=match_uuid,
            approved_actual_id=actual_uuid,
            schedule_activity_id=sched_uuid,
        )
        metadata = {
            "actual_quantity": actual.actual_quantity,
            "actual_unit": actual.actual_unit,
            "actual_date": actual.actual_date.isoformat(),
            "is_modified": actual.is_modified,
            "notes": actual.notes,
        }

        event_id = uuid5(actual_uuid, f"APPROVED_ACTUAL_COMMITTED:{actual.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.APPROVED_ACTUAL_COMMITTED,
            entity_type="approved_actual",
            entity_id=actual_uuid,
            actor=actor,
            action="COMMIT_ACTUAL",
            timestamp=actual.approved_at or actual.created_at,
            summary=f"Official approved actual committed ({actual.actual_quantity or 0} {actual.actual_unit or ''} on {actual.actual_date})",
            metadata=metadata,
            provenance_ref=provenance,
        )

    def normalize_dependency_edge(self, dep: DependencyResponse) -> AuditEvent:
        """
        Projects a ScheduleDependency edge into an AuditEvent.
        Represents current network edge state.
        """
        proj_uuid = _parse_uuid(dep.project_id)
        dep_uuid = _parse_uuid(dep.id)
        pred_uuid = _parse_uuid(dep.predecessor_id)
        succ_uuid = _parse_uuid(dep.successor_id)

        actor = AuditActor(
            actor_id=None,
            actor_name=None,
            actor_email=None,
            role="planner",
            is_system=False,
        )
        provenance = AuditProvenanceRef(
            schedule_activity_id=pred_uuid,
        )
        metadata = {
            "predecessor_id": str(pred_uuid),
            "successor_id": str(succ_uuid),
            "relationship_type": dep.relationship_type.value,
            "lag_days": dep.lag_days,
            "note": "Represents established schedule dependency edge",
        }

        event_id = uuid5(dep_uuid, f"DEPENDENCY_EDGE_MUTATED:{dep.created_at.isoformat()}")

        return AuditEvent(
            id=event_id,
            project_id=proj_uuid,
            event_type=AuditEventType.DEPENDENCY_EDGE_MUTATED,
            entity_type="schedule_dependency",
            entity_id=dep_uuid,
            actor=actor,
            action="ESTABLISH_EDGE",
            timestamp=dep.created_at,
            summary=f"Schedule dependency edge established: {pred_uuid} -> {succ_uuid} ({dep.relationship_type.value}, lag={dep.lag_days})",
            metadata=metadata,
            provenance_ref=provenance,
        )

    # ==========================================================================
    # 2. Audit Stream Query & Filtering
    # ==========================================================================

    async def list_audit_events(
        self,
        project_id: str | UUID,
        params: Optional[AuditFilterParams] = None,
    ) -> AuditEventListResponse:
        """
        Gathers, normalizes, filters, and paginates all domain lifecycle events for a project.
        Ordering is strictly deterministic: (timestamp DESC, event_type ASC, entity_id ASC, id ASC).
        """
        proj_uuid = _parse_uuid(project_id)
        proj_str = str(proj_uuid)
        filter_params = params or AuditFilterParams()

        all_events: list[AuditEvent] = []

        # 1. Field Inputs
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.FIELD_INPUT_SUBMITTED:
            inputs_resp = self.input_service.list_inputs(proj_str, limit=10000, offset=0)
            for inp in inputs_resp.inputs:
                all_events.append(self.normalize_field_input(inp))

        # 2. AI Extractions
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.AI_EXTRACTION_COMPLETED:
            extractions_resp = await self.extraction_service.list_extractions(proj_str, limit=10000, offset=0)
            for ext in extractions_resp.extractions:
                all_events.append(self.normalize_ai_extraction(ext))

        # 3. AI Matches (gathered across project extractions)
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.AI_MATCH_GENERATED:
            extractions_resp = await self.extraction_service.list_extractions(proj_str, limit=10000, offset=0)
            for ext in extractions_resp.extractions:
                matches = await self.matching_service.repository.list_matches(proj_uuid, _parse_uuid(ext.id))
                for match in matches:
                    all_events.append(self.normalize_ai_match(match))

        # 4. Planner Decisions
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.PLANNER_DECISION_RECORDED:
            decisions = await self.decision_service.decision_repo.list_decisions(proj_uuid)
            for dec in decisions:
                all_events.append(self.normalize_planner_decision(dec))

        # 5. Approved Actuals
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.APPROVED_ACTUAL_COMMITTED:
            actuals, _ = await self.decision_service.actual_repo.list_approved_actuals(proj_uuid, limit=10000, offset=0)
            for actual in actuals:
                all_events.append(self.normalize_approved_actual(actual))

        # 6. Schedule Dependencies
        if filter_params.event_type is None or filter_params.event_type == AuditEventType.DEPENDENCY_EDGE_MUTATED:
            deps = await self.dependency_service.list_dependencies(proj_uuid)
            for dep in deps:
                all_events.append(self.normalize_dependency_edge(dep))

        # Filter events in-memory
        filtered: list[AuditEvent] = []
        for event in all_events:
            if event.project_id != proj_uuid:
                continue

            if filter_params.event_type and event.event_type != filter_params.event_type:
                continue

            if filter_params.actor_id and event.actor.actor_id != filter_params.actor_id:
                continue

            if filter_params.entity_type and event.entity_type.lower() != filter_params.entity_type.lower():
                continue

            if filter_params.entity_id and event.entity_id != filter_params.entity_id:
                continue

            if filter_params.start_date and event.timestamp < filter_params.start_date:
                continue

            if filter_params.end_date and event.timestamp > filter_params.end_date:
                continue

            filtered.append(event)

        # Deterministic sorting rule: timestamp DESC, event_type ASC, entity_id ASC, id ASC
        filtered.sort(
            key=lambda e: (
                -e.timestamp.timestamp(),
                e.event_type.value,
                str(e.entity_id),
                str(e.id),
            )
        )

        total = len(filtered)
        paginated = filtered[filter_params.offset : filter_params.offset + filter_params.limit]

        return AuditEventListResponse(
            items=paginated,
            total=total,
            limit=filter_params.limit,
            offset=filter_params.offset,
        )

    # ==========================================================================
    # 3. Provenance Chain Resolution
    # ==========================================================================

    async def resolve_provenance(
        self,
        project_id: str | UUID,
        entity_type: str | ProvenanceNodeType,
        entity_id: str | UUID,
    ) -> ProvenanceChain:
        """
        Deterministically constructs the complete upstream and downstream provenance graph
        for any entity in the project.
        Uses exact foreign key linkages only; never hallucinates connections.
        """
        proj_uuid = _parse_uuid(project_id)
        proj_str = str(proj_uuid)
        target_uuid = _parse_uuid(entity_id)

        # Normalize entity type enum
        if isinstance(entity_type, str):
            try:
                node_type = ProvenanceNodeType(entity_type.upper())
            except ValueError:
                raise UnsupportedProvenanceEntityTypeError(f"Unsupported provenance entity type '{entity_type}'")
        else:
            node_type = entity_type

        nodes: dict[str, ProvenanceNode] = {}
        links: list[ProvenanceLink] = []
        unresolved: list[str] = []

        # 1. Resolve Root Node and traverse upstream/downstream
        if node_type == ProvenanceNodeType.APPROVED_ACTUAL:
            await self._traverse_from_actual(proj_uuid, target_uuid, nodes, links, unresolved)
        elif node_type == ProvenanceNodeType.PLANNER_DECISION:
            await self._traverse_from_decision(proj_uuid, target_uuid, nodes, links, unresolved)
        elif node_type == ProvenanceNodeType.AI_MATCH:
            await self._traverse_from_match(proj_uuid, target_uuid, nodes, links, unresolved)
        elif node_type == ProvenanceNodeType.AI_EXTRACTION:
            await self._traverse_from_extraction(proj_uuid, target_uuid, nodes, links, unresolved)
        elif node_type == ProvenanceNodeType.FIELD_INPUT:
            await self._traverse_from_field_input(proj_uuid, target_uuid, nodes, links, unresolved)
        elif node_type in (ProvenanceNodeType.VARIANCE, ProvenanceNodeType.RISK):
            # Target is a schedule activity ID
            await self._traverse_from_activity(proj_uuid, target_uuid, nodes, links, unresolved, node_type)
        else:
            raise UnsupportedProvenanceEntityTypeError(f"Provenance traversal not supported for type '{node_type.value}'")

        root_node_key = f"{node_type.value}:{target_uuid}"
        if root_node_key not in nodes:
            raise AuditEntityNotFoundError(f"Root entity '{target_uuid}' of type '{node_type.value}' not found in project '{proj_str}'")

        is_complete = len(unresolved) == 0 and len(nodes) > 1

        return ProvenanceChain(
            project_id=proj_uuid,
            root_entity_type=node_type,
            root_entity_id=target_uuid,
            nodes=list(nodes.values()),
            links=links,
            is_complete=is_complete,
            unresolved_links=unresolved,
        )

    # --- Private Traversal Helpers ---

    async def _traverse_from_actual(
        self,
        project_id: UUID,
        actual_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
    ) -> None:
        actual = await self.decision_service.actual_repo.get_by_id(project_id, actual_id)
        if not actual:
            # Check if actual belongs to another project
            for rec in self.decision_service.actual_repo._actuals.values():
                if str(rec["id"]) == str(actual_id) and str(rec["project_id"]) != str(project_id):
                    raise CrossProjectAuditError(f"Approved actual '{actual_id}' belongs to project '{rec['project_id']}'")
            return

        if _parse_uuid(actual.project_id) != project_id:
            raise CrossProjectAuditError(f"Approved actual '{actual_id}' belongs to project '{actual.project_id}'")

        # 1. Add Approved Actual Node
        actual_key = f"APPROVED_ACTUAL:{actual.id}"
        nodes[actual_key] = ProvenanceNode(
            node_id=actual_key,
            node_type=ProvenanceNodeType.APPROVED_ACTUAL,
            entity_id=actual.id,
            title=f"Approved Actual: {actual.actual_quantity} {actual.actual_unit or ''}",
            status="MODIFIED" if actual.is_modified else "APPROVED",
            timestamp=actual.approved_at,
            details={
                "actual_quantity": actual.actual_quantity,
                "actual_unit": actual.actual_unit,
                "actual_date": actual.actual_date.isoformat(),
                "is_modified": actual.is_modified,
                "source_evidence": actual.source_evidence,
            },
        )

        # 2. Traverse Upstream Decision
        decision = await self.decision_service.decision_repo.get_latest_decision(project_id, actual.match_id)
        if decision:
            dec_key = f"PLANNER_DECISION:{decision.id}"
            nodes[dec_key] = ProvenanceNode(
                node_id=dec_key,
                node_type=ProvenanceNodeType.PLANNER_DECISION,
                entity_id=decision.id,
                title=f"Planner Review ({decision.decision.value.upper()})",
                status=decision.decision.value.upper(),
                timestamp=decision.decided_at,
                details={
                    "decision": decision.decision.value,
                    "decided_by": str(decision.decided_by),
                    "rejection_reason": decision.rejection_reason,
                    "modified_payload": decision.modified_payload,
                },
            )
            links.append(ProvenanceLink(source_node_id=dec_key, target_node_id=actual_key, relationship="COMMITS_TO"))
        else:
            unresolved.append(f"No planner decision record found for match '{actual.match_id}'")

        # 3. Traverse Upstream Match
        match = await self.matching_service.repository.get_match(project_id, actual.match_id)
        if match:
            match_key = f"AI_MATCH:{match.id}"
            nodes[match_key] = ProvenanceNode(
                node_id=match_key,
                node_type=ProvenanceNodeType.AI_MATCH,
                entity_id=match.id,
                title=f"AI Match Recommendation: {match.recommended_activity_code or match.recommended_activity_id}",
                status=f"Confidence: {match.confidence_score}",
                timestamp=match.created_at,
                details={
                    "confidence_score": match.confidence_score,
                    "recommended_activity_id": str(match.recommended_activity_id),
                    "scoring_breakdown": match.scoring_breakdown.model_dump(),
                },
            )
            if decision:
                dec_key = f"PLANNER_DECISION:{decision.id}"
                links.append(ProvenanceLink(source_node_id=match_key, target_node_id=dec_key, relationship="EVALUATED_BY"))
        else:
            unresolved.append(f"No AI match record found for ID '{actual.match_id}'")

        # 4. Traverse Upstream Extraction
        extraction = await self.extraction_service.get_extraction(str(project_id), str(actual.extraction_id))
        if extraction:
            ext_key = f"AI_EXTRACTION:{extraction.id}"
            nodes[ext_key] = ProvenanceNode(
                node_id=ext_key,
                node_type=ProvenanceNodeType.AI_EXTRACTION,
                entity_id=_parse_uuid(extraction.id),
                title=f"AI Extraction ({extraction.model_version})",
                status=extraction.status.value,
                timestamp=extraction.created_at,
                details={
                    "confidence_score": extraction.confidence_score,
                    "model_version": extraction.model_version,
                    "status": extraction.status.value,
                },
            )
            if match:
                match_key = f"AI_MATCH:{match.id}"
                links.append(ProvenanceLink(source_node_id=ext_key, target_node_id=match_key, relationship="MATCHED_INTO"))

            # 5. Traverse Upstream Field Input
            inp = self.input_service.get_input(str(project_id), str(extraction.field_input_id))
            if inp:
                inp_key = f"FIELD_INPUT:{inp.id}"
                nodes[inp_key] = ProvenanceNode(
                    node_id=inp_key,
                    node_type=ProvenanceNodeType.FIELD_INPUT,
                    entity_id=_parse_uuid(inp.id),
                    title=f"Field Input ({inp.input_type.value.upper()})",
                    status="SUBMITTED",
                    timestamp=inp.created_at,
                    details={
                        "input_type": inp.input_type.value,
                        "title": inp.title,
                        "submitted_by_email": inp.submitted_by_email,
                        "field_date": inp.field_date.isoformat(),
                    },
                )
                links.append(ProvenanceLink(source_node_id=inp_key, target_node_id=ext_key, relationship="EXTRACTED_BY"))
            else:
                unresolved.append(f"No Field Input record found for extraction '{extraction.id}'")
        else:
            unresolved.append(f"No AI Extraction record found for ID '{actual.extraction_id}'")

        # 6. Traverse Downstream Variance & Risk (for the schedule activity)
        await self._attach_downstream_activity_nodes(project_id, actual.schedule_activity_id, actual_key, nodes, links)

    async def _traverse_from_decision(
        self,
        project_id: UUID,
        decision_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
    ) -> None:
        decisions = await self.decision_service.decision_repo.list_decisions(project_id)
        decision = next((d for d in decisions if d.id == decision_id), None)
        if not decision:
            return

        dec_key = f"PLANNER_DECISION:{decision.id}"
        nodes[dec_key] = ProvenanceNode(
            node_id=dec_key,
            node_type=ProvenanceNodeType.PLANNER_DECISION,
            entity_id=decision.id,
            title=f"Planner Review ({decision.decision.value.upper()})",
            status=decision.decision.value.upper(),
            timestamp=decision.decided_at,
            details={
                "decision": decision.decision.value,
                "decided_by": str(decision.decided_by),
                "rejection_reason": decision.rejection_reason,
            },
        )

        # Traverse Downstream Approved Actual if approved or modified
        if decision.decision in (PlannerDecisionType.APPROVED, PlannerDecisionType.MODIFIED):
            actuals, _ = await self.decision_service.actual_repo.list_approved_actuals(project_id, limit=1000)
            actual = next((a for a in actuals if a.match_id == decision.match_id), None)
            if actual:
                actual_key = f"APPROVED_ACTUAL:{actual.id}"
                nodes[actual_key] = ProvenanceNode(
                    node_id=actual_key,
                    node_type=ProvenanceNodeType.APPROVED_ACTUAL,
                    entity_id=actual.id,
                    title=f"Approved Actual: {actual.actual_quantity} {actual.actual_unit or ''}",
                    status="MODIFIED" if actual.is_modified else "APPROVED",
                    timestamp=actual.approved_at,
                    details={"actual_quantity": actual.actual_quantity, "actual_date": actual.actual_date.isoformat()},
                )
                links.append(ProvenanceLink(source_node_id=dec_key, target_node_id=actual_key, relationship="COMMITS_TO"))
                await self._attach_downstream_activity_nodes(project_id, actual.schedule_activity_id, actual_key, nodes, links)
            else:
                unresolved.append(f"No approved actual record found for approved match '{decision.match_id}'")
        else:
            # Rejection terminates the chain cleanly
            unresolved.append(f"Planner decision was REJECTED; approved actual deliberately not committed")

        # Traverse Upstream Match & Extraction
        match = await self.matching_service.repository.get_match(project_id, decision.match_id)
        if match:
            match_key = f"AI_MATCH:{match.id}"
            nodes[match_key] = ProvenanceNode(
                node_id=match_key,
                node_type=ProvenanceNodeType.AI_MATCH,
                entity_id=match.id,
                title=f"AI Match Recommendation: {match.recommended_activity_code or match.recommended_activity_id}",
                status=f"Confidence: {match.confidence_score}",
                timestamp=match.created_at,
                details={"confidence_score": match.confidence_score},
            )
            links.append(ProvenanceLink(source_node_id=match_key, target_node_id=dec_key, relationship="EVALUATED_BY"))

            extraction = await self.extraction_service.get_extraction(str(project_id), str(match.extraction_id))
            if extraction:
                ext_key = f"AI_EXTRACTION:{extraction.id}"
                nodes[ext_key] = ProvenanceNode(
                    node_id=ext_key,
                    node_type=ProvenanceNodeType.AI_EXTRACTION,
                    entity_id=_parse_uuid(extraction.id),
                    title=f"AI Extraction ({extraction.model_version})",
                    status=extraction.status.value,
                    timestamp=extraction.created_at,
                    details={"confidence_score": extraction.confidence_score},
                )
                links.append(ProvenanceLink(source_node_id=ext_key, target_node_id=match_key, relationship="MATCHED_INTO"))

                inp = self.input_service.get_input(str(project_id), str(extraction.field_input_id))
                if inp:
                    inp_key = f"FIELD_INPUT:{inp.id}"
                    nodes[inp_key] = ProvenanceNode(
                        node_id=inp_key,
                        node_type=ProvenanceNodeType.FIELD_INPUT,
                        entity_id=_parse_uuid(inp.id),
                        title=f"Field Input ({inp.input_type.value.upper()})",
                        status="SUBMITTED",
                        timestamp=inp.created_at,
                        details={"title": inp.title, "input_type": inp.input_type.value},
                    )
                    links.append(ProvenanceLink(source_node_id=inp_key, target_node_id=ext_key, relationship="EXTRACTED_BY"))

    async def _traverse_from_match(
        self,
        project_id: UUID,
        match_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
    ) -> None:
        match = await self.matching_service.repository.get_match(project_id, match_id)
        if not match:
            return

        match_key = f"AI_MATCH:{match.id}"
        nodes[match_key] = ProvenanceNode(
            node_id=match_key,
            node_type=ProvenanceNodeType.AI_MATCH,
            entity_id=match.id,
            title=f"AI Match: {match.recommended_activity_code or match.recommended_activity_id}",
            status=f"Confidence: {match.confidence_score}",
            timestamp=match.created_at,
            details={"confidence_score": match.confidence_score},
        )

        # Upstream Extraction & Input
        extraction = await self.extraction_service.get_extraction(str(project_id), str(match.extraction_id))
        if extraction:
            ext_key = f"AI_EXTRACTION:{extraction.id}"
            nodes[ext_key] = ProvenanceNode(
                node_id=ext_key,
                node_type=ProvenanceNodeType.AI_EXTRACTION,
                entity_id=_parse_uuid(extraction.id),
                title=f"AI Extraction ({extraction.model_version})",
                status=extraction.status.value,
                timestamp=extraction.created_at,
                details={"confidence_score": extraction.confidence_score},
            )
            links.append(ProvenanceLink(source_node_id=ext_key, target_node_id=match_key, relationship="MATCHED_INTO"))

            inp = self.input_service.get_input(str(project_id), str(extraction.field_input_id))
            if inp:
                inp_key = f"FIELD_INPUT:{inp.id}"
                nodes[inp_key] = ProvenanceNode(
                    node_id=inp_key,
                    node_type=ProvenanceNodeType.FIELD_INPUT,
                    entity_id=_parse_uuid(inp.id),
                    title=f"Field Input ({inp.input_type.value.upper()})",
                    status="SUBMITTED",
                    timestamp=inp.created_at,
                    details={"title": inp.title, "input_type": inp.input_type.value},
                )
                links.append(ProvenanceLink(source_node_id=inp_key, target_node_id=ext_key, relationship="EXTRACTED_BY"))

        # Downstream Decision & Actual
        decision = await self.decision_service.decision_repo.get_latest_decision(project_id, match.id)
        if decision:
            dec_key = f"PLANNER_DECISION:{decision.id}"
            nodes[dec_key] = ProvenanceNode(
                node_id=dec_key,
                node_type=ProvenanceNodeType.PLANNER_DECISION,
                entity_id=decision.id,
                title=f"Planner Decision ({decision.decision.value.upper()})",
                status=decision.decision.value.upper(),
                timestamp=decision.decided_at,
                details={"decision": decision.decision.value},
            )
            links.append(ProvenanceLink(source_node_id=match_key, target_node_id=dec_key, relationship="EVALUATED_BY"))

            if decision.decision in (PlannerDecisionType.APPROVED, PlannerDecisionType.MODIFIED):
                actuals, _ = await self.decision_service.actual_repo.list_approved_actuals(project_id, limit=1000)
                actual = next((a for a in actuals if a.match_id == match.id), None)
                if actual:
                    actual_key = f"APPROVED_ACTUAL:{actual.id}"
                    nodes[actual_key] = ProvenanceNode(
                        node_id=actual_key,
                        node_type=ProvenanceNodeType.APPROVED_ACTUAL,
                        entity_id=actual.id,
                        title=f"Approved Actual: {actual.actual_quantity} {actual.actual_unit or ''}",
                        status="APPROVED",
                        timestamp=actual.approved_at,
                        details={"actual_quantity": actual.actual_quantity},
                    )
                    links.append(ProvenanceLink(source_node_id=dec_key, target_node_id=actual_key, relationship="COMMITS_TO"))
                    await self._attach_downstream_activity_nodes(project_id, actual.schedule_activity_id, actual_key, nodes, links)

    async def _traverse_from_extraction(
        self,
        project_id: UUID,
        extraction_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
    ) -> None:
        extraction = await self.extraction_service.get_extraction(str(project_id), str(extraction_id))
        if not extraction:
            return

        ext_key = f"AI_EXTRACTION:{extraction.id}"
        nodes[ext_key] = ProvenanceNode(
            node_id=ext_key,
            node_type=ProvenanceNodeType.AI_EXTRACTION,
            entity_id=_parse_uuid(extraction.id),
            title=f"AI Extraction ({extraction.model_version})",
            status=extraction.status.value,
            timestamp=extraction.created_at,
            details={"confidence_score": extraction.confidence_score},
        )

        inp = self.input_service.get_input(str(project_id), str(extraction.field_input_id))
        if inp:
            inp_key = f"FIELD_INPUT:{inp.id}"
            nodes[inp_key] = ProvenanceNode(
                node_id=inp_key,
                node_type=ProvenanceNodeType.FIELD_INPUT,
                entity_id=_parse_uuid(inp.id),
                title=f"Field Input ({inp.input_type.value.upper()})",
                status="SUBMITTED",
                timestamp=inp.created_at,
                details={"title": inp.title, "input_type": inp.input_type.value},
            )
            links.append(ProvenanceLink(source_node_id=inp_key, target_node_id=ext_key, relationship="EXTRACTED_BY"))

        # Downstream Matches
        matches = await self.matching_service.repository.list_matches(project_id, extraction_id)
        for match in matches:
            match_key = f"AI_MATCH:{match.id}"
            nodes[match_key] = ProvenanceNode(
                node_id=match_key,
                node_type=ProvenanceNodeType.AI_MATCH,
                entity_id=match.id,
                title=f"AI Match: {match.recommended_activity_code or match.recommended_activity_id}",
                status=f"Confidence: {match.confidence_score}",
                timestamp=match.created_at,
                details={"confidence_score": match.confidence_score},
            )
            links.append(ProvenanceLink(source_node_id=ext_key, target_node_id=match_key, relationship="MATCHED_INTO"))

    async def _traverse_from_field_input(
        self,
        project_id: UUID,
        input_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
    ) -> None:
        inp = self.input_service.get_input(str(project_id), str(input_id))
        if not inp:
            return

        inp_key = f"FIELD_INPUT:{inp.id}"
        nodes[inp_key] = ProvenanceNode(
            node_id=inp_key,
            node_type=ProvenanceNodeType.FIELD_INPUT,
            entity_id=_parse_uuid(inp.id),
            title=f"Field Input ({inp.input_type.value.upper()})",
            status="SUBMITTED",
            timestamp=inp.created_at,
            details={"title": inp.title, "input_type": inp.input_type.value},
        )

        extraction = await self.extraction_service.get_extraction_by_input(str(project_id), str(input_id))
        if extraction:
            ext_key = f"AI_EXTRACTION:{extraction.id}"
            nodes[ext_key] = ProvenanceNode(
                node_id=ext_key,
                node_type=ProvenanceNodeType.AI_EXTRACTION,
                entity_id=_parse_uuid(extraction.id),
                title=f"AI Extraction ({extraction.model_version})",
                status=extraction.status.value,
                timestamp=extraction.created_at,
                details={"confidence_score": extraction.confidence_score},
            )
            links.append(ProvenanceLink(source_node_id=inp_key, target_node_id=ext_key, relationship="EXTRACTED_BY"))

    async def _traverse_from_activity(
        self,
        project_id: UUID,
        activity_id: UUID,
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
        unresolved: list[str],
        origin_type: ProvenanceNodeType,
    ) -> None:
        actuals, _ = await self.decision_service.actual_repo.list_approved_actuals(
            project_id, schedule_activity_id=activity_id, limit=1
        )
        if actuals:
            await self._traverse_from_actual(project_id, actuals[0].id, nodes, links, unresolved)
        else:
            # Anchor activity itself
            act = await self.schedule_service.get_activity(str(project_id), str(activity_id))
            if act:
                await self._attach_downstream_activity_nodes(project_id, activity_id, None, nodes, links)

    async def _attach_downstream_activity_nodes(
        self,
        project_id: UUID,
        schedule_activity_id: UUID,
        source_key: Optional[str],
        nodes: dict[str, ProvenanceNode],
        links: list[ProvenanceLink],
    ) -> None:
        """Fetches and attaches Phase 8 Variance and Phase 9 Risk assessment nodes for an activity."""
        try:
            variance_item = await self.variance_query_service.get_activity_variance(project_id, schedule_activity_id)
            if variance_item:
                var_key = f"VARIANCE:{schedule_activity_id}"
                nodes[var_key] = ProvenanceNode(
                    node_id=var_key,
                    node_type=ProvenanceNodeType.VARIANCE,
                    entity_id=schedule_activity_id,
                    title=f"Plan vs Actual Variance ({variance_item.activity_code})",
                    status=variance_item.variance_status.value,
                    timestamp=None,
                    details={
                        "progress_percent": variance_item.progress_percent,
                        "quantity_variance": variance_item.quantity_variance,
                        "date_variance_days": variance_item.date_variance_days,
                    },
                )
                if source_key:
                    links.append(ProvenanceLink(source_node_id=source_key, target_node_id=var_key, relationship="DRIVES_VARIANCE"))

                # Attach Risk node
                risk_item = await self.risk_query_service.get_activity_risk(project_id, schedule_activity_id)
                if risk_item:
                    risk_key = f"RISK:{schedule_activity_id}"
                    nodes[risk_key] = ProvenanceNode(
                        node_id=risk_key,
                        node_type=ProvenanceNodeType.RISK,
                        entity_id=schedule_activity_id,
                        title=f"Risk Intelligence (Score: {risk_item.risk_score})",
                        status=risk_item.severity.value,
                        timestamp=None,
                        details={
                            "severity": risk_item.severity.value,
                            "risk_score": risk_item.risk_score,
                            "is_critical_path": risk_item.is_critical_path,
                            "categories": [c.value for c in risk_item.categories],
                        },
                    )
                    links.append(ProvenanceLink(source_node_id=var_key, target_node_id=risk_key, relationship="INFORMS_RISK"))
        except Exception as err:
            logger.debug(f"Downstream variance/risk attachment skipped: {err}")


audit_service = AuditService()
