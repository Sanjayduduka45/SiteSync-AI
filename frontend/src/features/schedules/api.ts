/**
 * Schedule & AI Matching API Module — SiteSync AI Phase 6.7.
 * Interacts with backend API routes:
 *   - GET  /v1/projects/{projectId}/schedules/activities
 *   - POST /v1/projects/{projectId}/schedules/activities
 *   - POST /v1/projects/{projectId}/extractions/{extractionId}/match
 *   - GET  /v1/projects/{projectId}/extractions/{extractionId}/matches
 */

import { apiGet, apiPost } from '@/services/api'
import type {
  MatchRecommendationListResponse,
  ScheduleActivity,
  ScheduleActivityCreateInput,
  ScheduleActivityListResponse,
} from './types'

/**
 * Lists baseline schedule activities for a project.
 */
export async function getScheduleActivities(
  projectId: string,
  limit = 50,
  offset = 0
): Promise<ScheduleActivityListResponse> {
  return apiGet<ScheduleActivityListResponse>(
    `/v1/projects/${projectId}/schedules/activities?limit=${limit}&offset=${offset}`
  )
}

/**
 * Creates or idempotently upserts a baseline schedule activity.
 * Requires Planner or Admin role.
 */
export async function createScheduleActivity(
  projectId: string,
  data: ScheduleActivityCreateInput
): Promise<ScheduleActivity> {
  return apiPost<ScheduleActivity>(
    `/v1/projects/${projectId}/schedules/activities`,
    data
  )
}

/**
 * Triggers multi-factor AI schedule matching for an extraction.
 * Requires Planner or Admin role.
 */
export async function triggerExtractionMatching(
  projectId: string,
  extractionId: string
): Promise<MatchRecommendationListResponse> {
  return apiPost<MatchRecommendationListResponse>(
    `/v1/projects/${projectId}/extractions/${extractionId}/match`,
    {}
  )
}

/**
 * Retrieves match recommendations for an extraction.
 * Requires Viewer role or above.
 */
export async function getExtractionMatches(
  projectId: string,
  extractionId: string
): Promise<MatchRecommendationListResponse> {
  return apiGet<MatchRecommendationListResponse>(
    `/v1/projects/${projectId}/extractions/${extractionId}/matches`
  )
}
