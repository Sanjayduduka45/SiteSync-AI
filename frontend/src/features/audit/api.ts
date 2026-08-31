/**
 * Audit & Provenance API Client — SiteSync AI Phase 10.4.
 * Interacts with read-only Phase 10.3 backend endpoints:
 *   - GET /api/v1/projects/{projectId}/audit
 *   - GET /api/v1/projects/{projectId}/audit/provenance/{entityType}/{entityId}
 */

import { apiGet } from '@/services/api'
import type {
  AuditEventListResponse,
  AuditFilterParams,
  ProvenanceChain,
} from './types'

/**
 * Retrieves paginated, deterministically sorted audit events for a project.
 */
export async function getAuditEvents(
  projectId: string,
  filters: AuditFilterParams = {}
): Promise<AuditEventListResponse> {
  const params = new URLSearchParams()
  params.append('limit', String(filters.limit ?? 50))
  params.append('offset', String(filters.offset ?? 0))

  if (filters.event_type && filters.event_type !== 'all') {
    params.append('event_type', filters.event_type)
  }
  if (filters.entity_type && filters.entity_type.trim()) {
    params.append('entity_type', filters.entity_type.trim())
  }
  if (filters.actor_id && filters.actor_id.trim()) {
    params.append('actor_id', filters.actor_id.trim())
  }
  if (filters.entity_id && filters.entity_id.trim()) {
    params.append('entity_id', filters.entity_id.trim())
  }
  if (filters.start_date && filters.start_date.trim()) {
    params.append('start_date', filters.start_date.trim())
  }
  if (filters.end_date && filters.end_date.trim()) {
    params.append('end_date', filters.end_date.trim())
  }

  return apiGet<AuditEventListResponse>(
    `/v1/projects/${projectId}/audit?${params.toString()}`
  )
}

/**
 * Retrieves the complete field-to-schedule provenance lineage graph for an entity.
 */
export async function getProvenance(
  projectId: string,
  entityType: string,
  entityId: string
): Promise<ProvenanceChain> {
  return apiGet<ProvenanceChain>(
    `/v1/projects/${projectId}/audit/provenance/${encodeURIComponent(entityType.toLowerCase())}/${encodeURIComponent(entityId)}`
  )
}

/**
 * Formats API errors safely to human-readable text without exposing internal details.
 */
export function formatAuditError(err: unknown): string {
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
      msg.toLowerCase().includes('tenant')
    ) {
      return 'You do not have permission to view audit history for this project.'
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'The requested audit or provenance record could not be found.'
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
      return 'Unable to load audit history. Please try again.'
    }
    return msg
  }
  return 'Unable to load audit history. Please try again.'
}
