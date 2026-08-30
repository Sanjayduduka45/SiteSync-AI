import { apiDelete, apiGet, apiPost } from '@/services/api'
import type { CreateReportInput, Report, ReportListResponse } from './types'

export async function fetchReports(projectId: string): Promise<ReportListResponse> {
  return apiGet<ReportListResponse>(`/v1/projects/${projectId}/reports`)
}

export async function fetchReport(projectId: string, reportId: string): Promise<Report> {
  return apiGet<Report>(`/v1/projects/${projectId}/reports/${reportId}`)
}

export async function createReport(projectId: string, payload: CreateReportInput): Promise<Report> {
  return apiPost<Report>(`/v1/projects/${projectId}/reports`, payload)
}

export async function deleteReport(projectId: string, reportId: string): Promise<{ status: string; id: string }> {
  return apiDelete<{ status: string; id: string }>(`/v1/projects/${projectId}/reports/${reportId}`)
}
