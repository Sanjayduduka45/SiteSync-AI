/**
 * SiteSync AI — Phase 10.4 Audit & Provenance Domain Types.
 * Strictly mirrors backend schemas in app/schemas/audit.py (ADR-019, ADR-020, ADR-021).
 */

export type AuditEventType =
  | 'FIELD_INPUT_SUBMITTED'
  | 'AI_EXTRACTION_COMPLETED'
  | 'AI_MATCH_GENERATED'
  | 'PLANNER_DECISION_RECORDED'
  | 'APPROVED_ACTUAL_COMMITTED'
  | 'DEPENDENCY_EDGE_MUTATED'

export type AuditAction =
  | 'SUBMIT'
  | 'EXTRACT'
  | 'RECOMMEND'
  | 'APPROVE'
  | 'REJECT'
  | 'MODIFY'
  | 'COMMIT_ACTUAL'
  | 'ESTABLISH_EDGE'
  | 'DELETE_EDGE'

export type ProvenanceNodeType =
  | 'FIELD_INPUT'
  | 'AI_EXTRACTION'
  | 'AI_MATCH'
  | 'PLANNER_DECISION'
  | 'APPROVED_ACTUAL'
  | 'VARIANCE'
  | 'RISK'

export interface AuditActor {
  actor_id?: string | null
  actor_name?: string | null
  actor_email?: string | null
  role?: string | null
  is_system: boolean
}

export interface AuditProvenanceRef {
  entity_type: string
  entity_id: string
  label?: string | null
}

export interface AuditEvent {
  id: string
  project_id: string
  event_type: AuditEventType
  action: AuditAction
  entity_type: string
  entity_id: string
  timestamp: string
  actor: AuditActor
  provenance_refs: AuditProvenanceRef[]
  payload_summary: Record<string, unknown>
}

export interface AuditFilterParams {
  limit?: number
  offset?: number
  event_type?: AuditEventType | 'all'
  entity_type?: string
  actor_id?: string
  entity_id?: string
  start_date?: string
  end_date?: string
}

export interface AuditEventListResponse {
  items: AuditEvent[]
  total: number
  limit: number
  offset: number
}

export interface ProvenanceNode {
  node_id: string
  node_type: ProvenanceNodeType
  entity_id: string
  title: string
  status?: string | null
  timestamp?: string | null
  details: Record<string, unknown>
}

export interface ProvenanceLink {
  source_node_id: string
  target_node_id: string
  relationship: string
}

export interface ProvenanceChain {
  project_id: string
  root_entity_type: ProvenanceNodeType
  root_entity_id: string
  nodes: ProvenanceNode[]
  links: ProvenanceLink[]
  is_complete: boolean
  unresolved_links: string[]
}
