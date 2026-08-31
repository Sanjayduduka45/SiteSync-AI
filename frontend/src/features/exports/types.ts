/**
 * SiteSync AI — Phase 10.5 Report Export Types.
 * Strictly reflects ADR-019 and backend export schemas in backend/app/schemas/export.py.
 */

export type ExportDataset = 'approved_actuals' | 'variance' | 'risk_register'
export type ExportFormat = 'csv' | 'json'

export interface ExportActionOptions {
  projectId: string
  dataset: ExportDataset
  format: ExportFormat
}
