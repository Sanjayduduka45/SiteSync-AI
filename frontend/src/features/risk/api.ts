/**
 * Risk and Critical Path API Client — SiteSync AI Phase 9.6.
 * Interacts with read-only Phase 9.5 backend endpoints:
 *   - GET /v1/projects/{projectId}/network/critical-path
 *   - GET /v1/projects/{projectId}/risks/summary
 *   - GET /v1/projects/{projectId}/risks/activities
 *   - GET /v1/projects/{projectId}/risks/downstream-impact/{activityId}
 */

import { apiGet } from '@/services/api'
import type {
  ActivityRiskListResponse,
  CriticalPathResponse,
  DownstreamImpactResult,
  ProjectRiskSummary,
  RiskFilterParams,
} from './types'

/**
 * Retrieves aggregated project-level risk intelligence and severity taxonomy distribution.
 */
export async function getRiskSummary(projectId: string): Promise<ProjectRiskSummary> {
  return apiGet<ProjectRiskSummary>(`/v1/projects/${projectId}/risks/summary`)
}

/**
 * Retrieves calculated Critical Path Method (CPM) metrics and node sequences for a project.
 */
export async function getCriticalPath(projectId: string): Promise<CriticalPathResponse> {
  return apiGet<CriticalPathResponse>(`/v1/projects/${projectId}/network/critical-path`)
}

/**
 * Retrieves paginated schedule activity risk assessments with server-side filtering.
 */
export async function getRiskActivities(
  projectId: string,
  filters: RiskFilterParams = {}
): Promise<ActivityRiskListResponse> {
  const params = new URLSearchParams()
  params.append('limit', String(filters.limit ?? 50))
  params.append('offset', String(filters.offset ?? 0))

  if (filters.severity && filters.severity !== 'all') {
    params.append('severity', filters.severity)
  }
  if (filters.category && filters.category !== 'all') {
    params.append('category', filters.category)
  }
  if (filters.wbs_code && filters.wbs_code.trim()) {
    params.append('wbs_code', filters.wbs_code.trim())
  }
  if (filters.discipline && filters.discipline.trim()) {
    params.append('discipline', filters.discipline.trim())
  }

  return apiGet<ActivityRiskListResponse>(
    `/v1/projects/${projectId}/risks/activities?${params.toString()}`
  )
}

/**
 * Retrieves transitive downstream delay impact and float erosion tree for a specific schedule activity.
 */
export async function getDownstreamImpact(
  projectId: string,
  activityId: string
): Promise<DownstreamImpactResult> {
  return apiGet<DownstreamImpactResult>(
    `/v1/projects/${projectId}/risks/downstream-impact/${activityId}`
  )
}

/**
 * Formats API errors safely to human-readable text without exposing internal details.
 */
export function formatRiskError(err: unknown): string {
  if (err instanceof Error) {
    const msg = err.message
    if (
      msg.includes('401') ||
      msg.toLowerCase().includes('unauthorized') ||
      msg.toLowerCase().includes('token')
    ) {
      return 'Your session has expired. Please sign in again.'
    }
    if (
      msg.includes('403') ||
      msg.toLowerCase().includes('forbidden') ||
      msg.toLowerCase().includes('permission') ||
      msg.toLowerCase().includes('tenant_violation')
    ) {
      return "You don't have permission to view project risks."
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'Risk data could not be found.'
    }
    if (
      msg.includes('500') ||
      msg.toLowerCase().includes('internal') ||
      msg.includes('secret') ||
      msg.includes('key') ||
      msg.includes('jwt') ||
      msg.includes('vector') ||
      msg.includes('Traceback') ||
      msg.includes('File "')
    ) {
      return 'Unable to load risk intelligence. Please try again.'
    }
    return msg
  }
  return 'Unable to load risk intelligence. Please try again.'
}
