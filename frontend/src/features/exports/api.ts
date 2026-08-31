/**
 * Report Export API Client — SiteSync AI Phase 10.5.
 * Interacts with read-only Phase 10.3 backend export endpoints:
 *   GET /api/v1/projects/{projectId}/exports/{dataset}?format={csv|json}
 */

import { apiDownload } from '@/services/api'
import type { ExportDataset, ExportFormat } from './types'

/**
 * Downloads a complete unpaginated dataset export from the backend.
 */
export async function downloadExport(
  projectId: string,
  dataset: ExportDataset,
  format: ExportFormat = 'csv'
): Promise<void> {
  const { blob, filename } = await apiDownload(
    `/v1/projects/${projectId}/exports/${dataset}?format=${format}`
  )

  const fallbackFilename = `${dataset}_${projectId}.${format}`
  const finalFilename = filename || fallbackFilename

  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.style.display = 'none'
  a.href = url
  a.download = finalFilename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

/**
 * Formats export API errors safely without exposing internal details.
 */
export function formatExportError(err: unknown): string {
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
      return 'You do not have permission to export project data.'
    }
    if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
      return 'The requested export dataset could not be found.'
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
      return 'Unable to generate export. Please try again.'
    }
    return msg
  }
  return 'Unable to generate export. Please try again.'
}
