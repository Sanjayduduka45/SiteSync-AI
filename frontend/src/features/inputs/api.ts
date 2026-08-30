/**
 * Field Inputs API client — SiteSync AI Phase 4.
 */

import { apiDelete, apiGet, apiPost, apiUpload } from '@/services/api'
import type {
  CreateTextInputPayload,
  FieldInput,
  FieldInputListResponse,
  UploadMediaInputPayload,
} from './types'

export async function fetchFieldInputs(
  projectId: string,
  params?: {
    input_type?: string
    field_date?: string
    limit?: number
    offset?: number
  }
): Promise<FieldInputListResponse> {
  const query = new URLSearchParams()
  if (params?.input_type && params.input_type !== 'all') {
    query.set('input_type', params.input_type)
  }
  if (params?.field_date) {
    query.set('field_date', params.field_date)
  }
  if (params?.limit) {
    query.set('limit', String(params.limit))
  }
  if (params?.offset) {
    query.set('offset', String(params.offset))
  }

  const qs = query.toString() ? `?${query.toString()}` : ''
  return apiGet<FieldInputListResponse>(`/v1/projects/${projectId}/inputs${qs}`)
}

export async function fetchFieldInput(projectId: string, inputId: string): Promise<FieldInput> {
  return apiGet<FieldInput>(`/v1/projects/${projectId}/inputs/${inputId}`)
}

export async function createTextInput(
  projectId: string,
  payload: CreateTextInputPayload
): Promise<FieldInput> {
  return apiPost<FieldInput>(`/v1/projects/${projectId}/inputs/text`, payload)
}

export async function uploadMediaInput(
  projectId: string,
  payload: UploadMediaInputPayload
): Promise<FieldInput> {
  const formData = new FormData()
  const filename = payload.filename || (payload.file instanceof File ? payload.file.name : `upload_${payload.input_type}`)
  formData.append('file', payload.file, filename)
  formData.append('input_type', payload.input_type)

  if (payload.title) {
    formData.append('title', payload.title)
  }
  if (payload.raw_text) {
    formData.append('raw_text', payload.raw_text)
  }
  if (payload.field_date) {
    formData.append('field_date', payload.field_date)
  }

  return apiUpload<FieldInput>(`/v1/projects/${projectId}/inputs/upload`, formData)
}

export async function deleteFieldInput(
  projectId: string,
  inputId: string
): Promise<{ status: string; id: string }> {
  return apiDelete<{ status: string; id: string }>(`/v1/projects/${projectId}/inputs/${inputId}`)
}
