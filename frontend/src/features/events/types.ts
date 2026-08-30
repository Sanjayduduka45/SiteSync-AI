export type FieldEventStatus =
  | 'pending'
  | 'processed'
  | 'matched'
  | 'needs_review'
  | 'approved'
  | 'rejected'

export interface FieldEvent {
  id: string
  project_id: string
  report_id?: string | null
  report_name?: string | null
  event_type: string
  description: string
  discipline: string
  location: string
  event_date: string
  progress_percent: number
  status: FieldEventStatus
  extracted_by?: string | null
  created_at: string
  updated_at: string
}

export interface FieldEventListResponse {
  events: FieldEvent[]
  total: number
}

export interface CreateEventInput {
  report_id?: string | null
  event_type: string
  description: string
  discipline: string
  location: string
  event_date: string
  progress_percent: number
}

export interface UpdateEventInput {
  event_type?: string
  description?: string
  discipline?: string
  location?: string
  event_date?: string
  progress_percent?: number
  status?: FieldEventStatus
}
