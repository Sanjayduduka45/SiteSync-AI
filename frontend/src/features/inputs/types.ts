/**
 * Field Inputs Domain Types — SiteSync AI Phase 4.
 */

export type FieldInputType = 'text' | 'voice' | 'photo' | 'document'

export type TranscriptionStatus = 'none' | 'pending' | 'completed' | 'failed'

export interface FieldInput {
  id: string
  project_id: string
  submitted_by: string
  submitted_by_email?: string | null
  input_type: FieldInputType
  title?: string | null
  raw_text?: string | null
  media_path?: string | null
  media_filename?: string | null
  media_mime_type?: string | null
  media_size_bytes: number
  media_url?: string | null
  audio_duration_seconds?: number | null
  transcription_status: TranscriptionStatus
  transcription_error?: string | null
  field_date: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface FieldInputListResponse {
  inputs: FieldInput[]
  total: number
}

export interface CreateTextInputPayload {
  title?: string
  raw_text: string
  field_date?: string
  metadata?: Record<string, unknown>
}

export interface UploadMediaInputPayload {
  file: File | Blob
  input_type: 'voice' | 'photo' | 'document'
  filename?: string
  title?: string
  raw_text?: string
  field_date?: string
}
