/**
 * Health check query key and fetch function.
 * Used by the status page to verify backend connectivity.
 */

import { apiGet } from '@/services/api'

export interface HealthResponse {
  status: string
  version: string
  environment: string
}

export const healthQueryKey = ['health'] as const

export function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/v1/health')
}
