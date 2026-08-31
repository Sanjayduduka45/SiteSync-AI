/**
 * Planner Decisions API Module — SiteSync AI Phase 7.5.
 * Interacts with backend Phase 7.4 endpoints:
 *   - POST /v1/projects/{projectId}/matches/{matchId}/approve
 *   - POST /v1/projects/{projectId}/matches/{matchId}/reject
 *   - POST /v1/projects/{projectId}/matches/{matchId}/modify
 *   - GET  /v1/projects/{projectId}/matches/{matchId}/decision
 *   - GET  /v1/projects/{projectId}/approved-actuals
 */

import { apiGet, apiPost } from '@/services/api'
import type {
  ApproveMatchRequest,
  ApprovedActualListResponse,
  ApprovedActualResponse,
  ModifyMatchRequest,
  PlannerDecisionResponse,
  RejectMatchRequest,
} from './types'

/**
 * Approves an AI match recommendation as-is and creates an approved actual.
 * Requires Planner or Admin role.
 */
export async function approveMatch(
  projectId: string,
  matchId: string,
  payload?: ApproveMatchRequest
): Promise<ApprovedActualResponse> {
  return apiPost<ApprovedActualResponse>(
    `/v1/projects/${projectId}/matches/${matchId}/approve`,
    payload?.notes ? { notes: payload.notes.trim() } : {}
  )
}

/**
 * Rejects an AI match recommendation with mandatory human reason.
 * Requires Planner or Admin role. Does not create an approved actual.
 */
export async function rejectMatch(
  projectId: string,
  matchId: string,
  payload: RejectMatchRequest
): Promise<PlannerDecisionResponse> {
  return apiPost<PlannerDecisionResponse>(
    `/v1/projects/${projectId}/matches/${matchId}/reject`,
    { rejection_reason: payload.rejection_reason.trim() }
  )
}

/**
 * Modifies an AI match recommendation before approval.
 * Requires Planner or Admin role.
 */
export async function modifyMatch(
  projectId: string,
  matchId: string,
  payload: ModifyMatchRequest
): Promise<ApprovedActualResponse> {
  return apiPost<ApprovedActualResponse>(
    `/v1/projects/${projectId}/matches/${matchId}/modify`,
    {
      schedule_activity_id: payload.schedule_activity_id,
      actual_quantity: payload.actual_quantity !== undefined && payload.actual_quantity !== null
        ? Number(payload.actual_quantity)
        : undefined,
      actual_unit: payload.actual_unit ? payload.actual_unit.trim() : undefined,
      actual_date: payload.actual_date,
      notes: payload.notes ? payload.notes.trim() : undefined,
    }
  )
}

/**
 * Retrieves the latest human planner decision for a match recommendation.
 * Requires Viewer role or above. Returns null if no decision exists.
 */
export async function getMatchDecision(
  projectId: string,
  matchId: string
): Promise<PlannerDecisionResponse | null> {
  return apiGet<PlannerDecisionResponse | null>(
    `/v1/projects/${projectId}/matches/${matchId}/decision`
  )
}

/**
 * Lists approved actual progress records for a project.
 * Requires Viewer role or above.
 */
export async function getApprovedActuals(
  projectId: string,
  limit = 50,
  offset = 0,
  scheduleActivityId?: string,
  fromDate?: string,
  toDate?: string
): Promise<ApprovedActualListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  if (scheduleActivityId) params.append('schedule_activity_id', scheduleActivityId)
  if (fromDate) params.append('from_date', fromDate)
  if (toDate) params.append('to_date', toDate)

  return apiGet<ApprovedActualListResponse>(
    `/v1/projects/${projectId}/approved-actuals?${params.toString()}`
  )
}

/**
 * Maps API errors safely to human-readable text without exposing internal details.
 */
export function formatDecisionError(err: unknown): string {
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
      return "You don't have permission to make planner decisions."
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'Recommendation not found.'
    }
    if (msg.includes('500') || msg.toLowerCase().includes('internal error')) {
      return 'Unable to save this decision. Please try again.'
    }
    // Sanitize any potential secret or stack trace leak
    if (
      msg.includes('secret') ||
      msg.includes('key') ||
      msg.includes('jwt') ||
      msg.includes('vector') ||
      msg.includes('Traceback') ||
      msg.includes('File "')
    ) {
      return 'An unexpected error occurred. Please try again.'
    }
    return msg
  }
  return 'Unable to save this decision. Please try again.'
}

/**
 * Formats errors for Approved Actuals page.
 */
export function formatApprovedActualsError(err: unknown): string {
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
      return "You don't have permission to view approved actuals."
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'Approved actuals could not be found.'
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
      return 'Unable to load approved actuals. Please try again.'
    }
    return msg
  }
  return 'Unable to load approved actuals. Please try again.'
}

