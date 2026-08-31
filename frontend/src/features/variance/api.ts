/**
 * Plan vs Actual Variance API Client — SiteSync AI Phase 8.3.
 * Interacts with read-only Phase 8.2 backend endpoints:
 *   - GET /v1/projects/{projectId}/variance/summary
 *   - GET /v1/projects/{projectId}/variance/activities
 *   - GET /v1/projects/{projectId}/variance/wbs
 */

import { apiGet } from '@/services/api'
import type {
  ActivityVarianceListResponse,
  ProjectVarianceSummary,
  VarianceFilterParams,
  WbsVarianceListResponse,
} from './types'

/**
 * Retrieves high-level project plan vs actual variance KPIs and rollups.
 */
export async function getVarianceSummary(projectId: string): Promise<ProjectVarianceSummary> {
  return apiGet<ProjectVarianceSummary>(`/v1/projects/${projectId}/variance/summary`)
}

/**
 * Lists paginated activity-level plan vs actual variance items with optional filtering.
 */
export async function getVarianceActivities(
  projectId: string,
  filters: VarianceFilterParams = {}
): Promise<ActivityVarianceListResponse> {
  const params = new URLSearchParams()
  params.append('limit', String(filters.limit ?? 50))
  params.append('offset', String(filters.offset ?? 0))

  if (filters.wbs_code && filters.wbs_code.trim()) {
    params.append('wbs_code', filters.wbs_code.trim())
  }
  if (filters.discipline && filters.discipline.trim()) {
    params.append('discipline', filters.discipline.trim())
  }
  if (filters.variance_status && filters.variance_status !== 'all') {
    params.append('variance_status', filters.variance_status)
  }
  if (filters.from_date) {
    params.append('from_date', filters.from_date)
  }
  if (filters.to_date) {
    params.append('to_date', filters.to_date)
  }

  return apiGet<ActivityVarianceListResponse>(
    `/v1/projects/${projectId}/variance/activities?${params.toString()}`
  )
}

/**
 * Retrieves WBS tier variance rollups grouped by homogeneous physical units.
 */
export async function getVarianceWbs(projectId: string): Promise<WbsVarianceListResponse> {
  return apiGet<WbsVarianceListResponse>(`/v1/projects/${projectId}/variance/wbs`)
}

/**
 * Formats API errors safely to human-readable text without exposing internal details.
 */
export function formatVarianceError(err: unknown): string {
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
      return "You don't have permission to view project variance."
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'Variance data could not be found.'
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
      return 'Unable to load Plan vs Actual data. Please try again.'
    }
    return msg
  }
  return 'Unable to load Plan vs Actual data. Please try again.'
}
