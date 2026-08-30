export type ReportStatus = 'uploaded' | 'processing' | 'processed' | 'failed'

export interface Report {
  id: string
  project_id: string
  name: string
  file_name: string
  file_type: string
  file_size: number
  source: string
  status: ReportStatus
  uploaded_by?: string | null
  uploaded_by_email?: string | null
  uploaded_at: string
  processed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ReportListResponse {
  reports: Report[]
  total: number
}

export interface CreateReportInput {
  name: string
  file_name: string
  file_type: string
  file_size?: number
  source?: string
}
