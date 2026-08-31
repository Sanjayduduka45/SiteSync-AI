/**
 * TypeScript Contracts for Human Planner Decisions & Approved Actuals — SiteSync AI Phase 7.5.
 * Strictly aligned with backend/app/schemas/decision.py.
 */

export type PlannerDecisionType = 'approved' | 'rejected' | 'modified'

export interface ApproveMatchRequest {
  notes?: string | null
}

export interface RejectMatchRequest {
  rejection_reason: string
}

export interface ModifyMatchRequest {
  schedule_activity_id: string
  actual_quantity?: number | null
  actual_unit?: string | null
  actual_date: string
  notes?: string | null
}

export interface PlannerDecisionResponse {
  id: string
  project_id: string
  match_id: string
  extraction_id: string
  decision: PlannerDecisionType
  decided_by: string
  decided_at: string
  rejection_reason?: string | null
  original_payload?: Record<string, unknown>
  modified_payload?: Record<string, unknown> | null
  created_at: string
}

export interface ApprovedActualResponse {
  id: string
  project_id: string
  schedule_activity_id: string
  extraction_id: string
  match_id: string
  activity_index: number
  actual_quantity?: number | null
  actual_unit?: string | null
  actual_date: string
  source_evidence?: unknown[]
  approved_by: string
  approved_at: string
  notes?: string | null
  is_modified: boolean
  created_at: string
  updated_at: string
}

export interface ApprovedActualListResponse {
  items: ApprovedActualResponse[]
  total: number
  limit: number
  offset: number
}
