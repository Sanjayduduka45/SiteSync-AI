/**
 * Plan vs Actual Variance Domain Types — SiteSync AI Phase 8.3.
 * Strictly mirrors backend Phase 8.2 response contracts.
 */

export type ActivityVarianceStatus =
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'over_delivered'
  | 'unquantified'
  | 'unit_mismatch'

export interface ActivityVarianceItem {
  activity_id: string
  project_id: string
  activity_code: string
  name: string
  wbs_code?: string | null
  discipline?: string | null
  location?: string | null

  // Baseline Plan
  planned_quantity?: number | null
  planned_unit?: string | null
  planned_start_date?: string | null
  planned_finish_date?: string | null

  // Human-Verified Actual
  actual_quantity_total?: number | null
  actual_unit?: string | null
  latest_actual_date?: string | null
  approved_actuals_count: number

  // Calculated Metrics (ADR-009)
  quantity_variance?: number | null
  progress_percent?: number | null
  date_variance_days?: number | null

  // Status & Flags (ADR-011, ADR-013)
  variance_status: ActivityVarianceStatus
  is_flagged: boolean
  flag_reason?: string | null
}

export interface ActivityVarianceListResponse {
  items: ActivityVarianceItem[]
  total: number
  limit: number
  offset: number
}

export interface UnitRollup {
  unit: string
  planned_total: number
  actual_total: number
  quantity_variance: number
  progress_percent?: number | null
  activity_count: number
}

export interface WbsRollup {
  wbs_code: string
  unit_rollups: UnitRollup[]
  unquantified_activity_count: number
  unit_mismatch_activity_count: number
  total_activity_count: number
}

export interface WbsVarianceListResponse {
  items: WbsRollup[]
  total: number
}

export interface ProjectVarianceSummary {
  project_id: string
  total_activities: number
  activities_with_progress: number
  completed_activities: number
  in_progress_activities: number
  not_started_activities: number
  over_delivered_activities: number
  unquantified_activities: number
  unit_mismatch_activities: number
  flagged_variance_count: number
  overall_progress_percent?: number | null
  unit_rollups: UnitRollup[]
}

export interface VarianceFilterParams {
  limit?: number
  offset?: number
  wbs_code?: string
  discipline?: string
  variance_status?: ActivityVarianceStatus | 'all'
  from_date?: string
  to_date?: string
}
