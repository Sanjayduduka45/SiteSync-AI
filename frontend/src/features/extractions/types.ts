/**
 * AI Extractions Domain Types — SiteSync AI Phase 5.
 */

export type ExtractionStatus = 'pending' | 'completed' | 'failed'

export type ConfidenceLevel = 'High' | 'Medium' | 'Low'

export interface ExtractedActivity {
  description: string
  progress_value?: number | null
  progress_unit?: string | null
  discipline?: string | null
  location?: string | null
  event_date?: string | null
  constraints?: string[]
  evidence_tokens?: string[]
}

export interface ExtractionResultData {
  raw_input_id?: string
  extracted_activities: ExtractedActivity[]
  extraction_confidence: number
  model_version: string
  processing_timestamp?: string
}

export interface ExtractionRecord {
  id: string
  project_id: string
  field_input_id: string
  status: ExtractionStatus
  extracted_data: ExtractionResultData | Record<string, unknown>
  confidence_score: number | null
  model_version: string
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ExtractionListResponse {
  extractions: ExtractionRecord[]
  total: number
}

export function getConfidenceLevel(score: number | null): { level: ConfidenceLevel; percentage: string } {
  if (score === null || score === undefined) {
    return { level: 'Low', percentage: 'N/A' }
  }
  const pct = Math.round(score * 100)
  if (score >= 0.85) {
    return { level: 'High', percentage: `${pct}%` }
  }
  if (score >= 0.60) {
    return { level: 'Medium', percentage: `${pct}%` }
  }
  return { level: 'Low', percentage: `${pct}%` }
}
