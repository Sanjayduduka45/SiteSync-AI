/**
 * TypeScript Contracts for Schedule Activities & AI Schedule Matching — SiteSync AI Phase 6.7.
 * Strictly aligned with backend/app/schemas/schedule.py.
 */

export type ProjectRole = 'admin' | 'planner' | 'supervisor' | 'viewer'

export interface ScheduleActivity {
  id: string
  project_id: string
  activity_code: string
  name: string
  wbs_code?: string | null
  discipline?: string | null
  location?: string | null
  planned_start_date?: string | null
  planned_finish_date?: string | null
  planned_quantity?: number | null
  planned_unit?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ScheduleActivityListResponse {
  items: ScheduleActivity[]
  total: number
  limit: number
  offset: number
}

export interface ScheduleActivityCreateInput {
  activity_code: string
  name: string
  wbs_code?: string | null
  discipline?: string | null
  location?: string | null
  planned_start_date?: string | null
  planned_finish_date?: string | null
  planned_quantity?: number | null
  planned_unit?: string | null
  metadata?: Record<string, unknown>
}

export type MatchConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW'

export interface ScoringBreakdown {
  semantic_similarity: number
  discipline_contribution: number
  location_contribution: number
  temporal_contribution: number
}

export interface AlternativeMatch {
  schedule_activity_id: string
  activity_code?: string | null
  activity_name?: string | null
  confidence_score: number
  discipline?: string | null
  location?: string | null
  planned_start_date?: string | null
  planned_finish_date?: string | null
  scoring_breakdown: ScoringBreakdown
}

export interface MatchRecommendation {
  id: string
  project_id: string
  extraction_id: string
  activity_index: number
  recommended_activity_id: string
  recommended_activity_code?: string | null
  recommended_activity_name?: string | null
  confidence_score: number
  scoring_breakdown: ScoringBreakdown
  alternative_matches: AlternativeMatch[]
  created_at: string
  updated_at: string
}

export interface MatchRecommendationListResponse {
  items: MatchRecommendation[]
  total: number
}

export function getMatchConfidenceBand(score: number): {
  level: MatchConfidenceLevel
  percentage: string
  label: string
} {
  const clamped = Math.max(0, Math.min(1, score))
  const percentage = `${Math.round(clamped * 100)}%`
  if (clamped >= 0.85) {
    return { level: 'HIGH', percentage, label: 'High' }
  }
  if (clamped >= 0.60) {
    return { level: 'MEDIUM', percentage, label: 'Medium' }
  }
  return { level: 'LOW', percentage, label: 'Low' }
}
