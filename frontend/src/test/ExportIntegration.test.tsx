/**
 * Tests for Phase 10.5 Frontend Export Action Integration and Security / Zero-Computation Boundaries.
 */

import { describe, it, expect } from 'vitest'

describe('Phase 10.5 Export Boundaries and Security Audit', () => {
  it('statically scans Phase 10.5 export runtime files to verify zero client-side calculation, sorting, or serialization engines', () => {
    const rawFiles = import.meta.glob<string>(
      ['../features/exports/**/*.ts', '../features/exports/**/*.tsx'],
      { query: '?raw', import: 'default', eager: true }
    )

    const forbiddenTokens = [
      'cpm',
      'forward_pass',
      'backward_pass',
      'topological_sort',
      'calculate_variance',
      'calculate_cpm',
      'compute_risk',
      'risk_score',
      'papaparse',
      'json.stringify(table',
    ]

    for (const [filePath, content] of Object.entries(rawFiles)) {
      const lower = content.toLowerCase()
      for (const token of forbiddenTokens) {
        expect(
          lower.includes(token),
          `Found forbidden calculation/serialization token "${token}" in export file: ${filePath}`
        ).toBe(false)
      }
    }
  })

  it('guarantees no sensitive credentials, system prompts, or secrets are exposed in export client', () => {
    const rawFiles = import.meta.glob<string>(
      ['../features/exports/**/*.ts', '../features/exports/**/*.tsx'],
      { query: '?raw', import: 'default', eager: true }
    )

    const forbiddenSecretTokens = [
      'service_role',
      'supabase_service_key',
      'password',
      'secret_key',
      'api_secret',
    ]

    for (const [filePath, content] of Object.entries(rawFiles)) {
      const lower = content.toLowerCase()
      for (const token of forbiddenSecretTokens) {
        expect(
          lower.includes(token),
          `Found forbidden sensitive token "${token}" in file: ${filePath}`
        ).toBe(false)
      }
    }
  })
})
