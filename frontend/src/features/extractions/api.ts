/**
 * AI Extractions API Module — SiteSync AI Phase 5.
 * Interacts with backend API routes:
 *   - POST /projects/{project_id}/inputs/{input_id}/extract
 *   - GET  /projects/{project_id}/inputs/{input_id}/extractions
 *   - GET  /projects/{project_id}/extractions
 */

import { apiGet, apiPost } from '@/services/api'
import type {
  ExtractionListResponse,
  ExtractionRecord,
  ExtractionStatus,
} from './types'

export interface ProjectExtractionFilters {
  status?: ExtractionStatus
  limit?: number
  offset?: number
}

/**
 * Triggers structured AI extraction on a raw field input.
 * Requires supervisor, planner, or admin role.
 */
export async function triggerExtraction(
  projectId: string,
  inputId: string
): Promise<ExtractionRecord> {
  return apiPost<ExtractionRecord>(
    `/v1/projects/${projectId}/inputs/${inputId}/extract`,
    {}
  )
}

/**
 * Retrieves extraction record(s) for a single field input.
 */
export async function getInputExtractions(
  projectId: string,
  inputId: string
): Promise<ExtractionListResponse> {
  return apiGet<ExtractionListResponse>(
    `/v1/projects/${projectId}/inputs/${inputId}/extractions`
  )
}

/**
 * Lists all AI extractions for a project with optional filters.
 */
export async function getProjectExtractions(
  projectId: string,
  filters?: ProjectExtractionFilters
): Promise<ExtractionListResponse> {
  const params = new URLSearchParams()
  if (filters?.status) params.append('status', filters.status)
  if (filters?.limit !== undefined) params.append('limit', String(filters.limit))
  if (filters?.offset !== undefined) params.append('offset', String(filters.offset))

  const queryString = params.toString()
  const path = queryString
    ? `/v1/projects/${projectId}/extractions?${queryString}`
    : `/v1/projects/${projectId}/extractions`

  return apiGet<ExtractionListResponse>(path)
}
