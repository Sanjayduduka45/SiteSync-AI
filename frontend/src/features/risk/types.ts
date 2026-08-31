/**
 * Risk and Critical Path TypeScript Definitions — SiteSync AI Phase 9.6.
 * Authoritative frontend contracts strictly mirroring Phase 9.5 backend models.
 */

export type RiskSeverityLevel = 'critical' | 'high' | 'medium' | 'low'

export type RiskCategory =
  | 'critical_path_delay'
  | 'float_erosion'
  | 'downstream_bottleneck'
  | 'predecessor_blocker'
  | 'unquantified_milestone_lag'
  | 'unit_mismatch_exposure'

export type DependencyRelationshipType = 'FS' | 'SS' | 'FF' | 'SF'

export type DownstreamImpactSeverity =
  | 'critical_slippage'
  | 'buffer_absorbed'
  | 'historical_completed'
  | 'unaffected'

export interface CPMActivityNodeResponse {
  activity_id: string
  project_id: string
  activity_code: string
  name: string
  wbs_code: string | null
  discipline: string | null
  location: string | null
  planned_start_date: string | null
  planned_finish_date: string | null
  duration_days: number
  early_start: string | null
  early_finish: string | null
  late_start: string | null
  late_finish: string | null
  total_float_days: number | null
  free_float_days: number | null
  is_critical: boolean
}

export interface CriticalPathResponse {
  project_id: string
  project_start_date: string | null
  project_finish_date: string | null
  total_activities: number
  critical_activities_count: number
  critical_path_activity_ids: string[]
  activities: CPMActivityNodeResponse[]
}

export interface ActivityRiskAssessment {
  activity_id: string
  project_id: string
  activity_code: string
  name: string
  wbs_code: string | null
  discipline: string | null
  location: string | null
  severity: RiskSeverityLevel
  risk_score: number
  categories: RiskCategory[]
  is_critical_path: boolean
  total_float: number | null
  date_variance_days: number | null
  direct_successors_count: number
  transitive_successors_count: number
  critical_slippage_successors_count: number
  variance_status: string | null
  progress_percent: number | null
  is_completed: boolean
}

export interface ProjectRiskSummary {
  project_id: string
  total_activities: number
  critical_severity_count: number
  high_severity_count: number
  medium_severity_count: number
  low_severity_count: number
  critical_path_delay_count: number
  float_erosion_count: number
  downstream_bottleneck_count: number
  predecessor_blocker_count: number
  unquantified_milestone_lag_count: number
  unit_mismatch_exposure_count: number
  average_risk_score: number | null
  items: ActivityRiskAssessment[]
}

export interface ActivityRiskListResponse {
  items: ActivityRiskAssessment[]
  total: number
  limit: number
  offset: number
}

export interface ImpactedSuccessorNode {
  activity_id: string
  activity_code: string
  name: string
  wbs_code: string | null
  discipline: string | null
  depth: number
  path: string[]
  relationship_with_immediate_predecessor: DependencyRelationshipType | null
  lag_days_with_immediate_predecessor: number
  planned_start_date: string | null
  planned_finish_date: string | null
  total_float: number | null
  free_float: number | null
  is_critical: boolean
  is_completed: boolean
  impact_severity: DownstreamImpactSeverity
  available_float: number | null
  float_consumed: number
  projected_delay_days: number
}

export interface DownstreamImpactResult {
  project_id: string
  source_activity_id: string
  source_activity_code: string
  source_name: string
  source_delay_days: number
  is_source_critical: boolean
  total_downstream_activities_count: number
  critical_slippage_count: number
  buffer_absorbed_count: number
  historical_completed_count: number
  impacted_successors: ImpactedSuccessorNode[]
}

export interface RiskFilterParams {
  limit?: number
  offset?: number
  severity?: string // 'all' | 'critical' | 'high' | 'medium' | 'low'
  category?: string // 'all' | RiskCategory
  wbs_code?: string
  discipline?: string
}
