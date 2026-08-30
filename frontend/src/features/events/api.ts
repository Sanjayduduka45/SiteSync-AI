import { apiGet, apiPatch, apiPost } from '@/services/api'
import type { CreateEventInput, FieldEvent, FieldEventListResponse, UpdateEventInput } from './types'

export async function fetchEvents(
  projectId: string,
  reportId?: string | null,
): Promise<FieldEventListResponse> {
  const query = reportId ? `?report_id=${encodeURIComponent(reportId)}` : ''
  return apiGet<FieldEventListResponse>(`/v1/projects/${projectId}/events${query}`)
}

export async function fetchEvent(projectId: string, eventId: string): Promise<FieldEvent> {
  return apiGet<FieldEvent>(`/v1/projects/${projectId}/events/${eventId}`)
}

export async function createEvent(projectId: string, payload: CreateEventInput): Promise<FieldEvent> {
  return apiPost<FieldEvent>(`/v1/projects/${projectId}/events`, payload)
}

export async function updateEvent(
  projectId: string,
  eventId: string,
  payload: UpdateEventInput,
): Promise<FieldEvent> {
  return apiPatch<FieldEvent>(`/v1/projects/${projectId}/events/${eventId}`, payload)
}
