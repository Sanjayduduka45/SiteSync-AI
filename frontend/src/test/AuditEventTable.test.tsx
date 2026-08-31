import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { AuditEventTable } from '@/features/audit/components/AuditEventTable'
import type { AuditEvent } from '@/features/audit/types'

describe('AuditEventTable', () => {
  const mockEvents: AuditEvent[] = [
    {
      id: 'event-1',
      project_id: '00000000-0000-0000-0000-000000000001',
      event_type: 'APPROVED_ACTUAL_COMMITTED',
      action: 'COMMIT_ACTUAL',
      entity_type: 'approved_actual',
      entity_id: 'act-uuid-1',
      timestamp: '2026-08-31T12:00:00Z',
      actor: {
        actor_id: 'user-1',
        actor_name: 'Planner Jane',
        actor_email: 'jane@sitesync.ai',
        role: 'planner',
        is_system: false,
      },
      provenance_refs: [],
      payload_summary: { actual_quantity: 50, actual_unit: 'LF' },
    },
    {
      id: 'event-2',
      project_id: '00000000-0000-0000-0000-000000000001',
      event_type: 'AI_EXTRACTION_COMPLETED',
      action: 'EXTRACT',
      entity_type: 'ai_extraction',
      entity_id: 'ext-uuid-1',
      timestamp: '2026-08-31T11:55:00Z',
      actor: {
        is_system: true,
      },
      provenance_refs: [],
      payload_summary: { model_version: 'gemini-1.5-pro' },
    },
  ]

  it('renders table columns, canonical event badges, and actor labels', () => {
    render(<AuditEventTable events={mockEvents} onViewProvenance={vi.fn()} />)

    expect(screen.getByText('Approved Actual')).toBeInTheDocument()
    expect(screen.getByText('AI Extraction')).toBeInTheDocument()
    expect(screen.getByText('Planner Jane')).toBeInTheDocument()
    expect(screen.getByText('SiteSync System')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /View Provenance/i }).length).toBe(2)
  })

  it('calls onViewProvenance with entity type and id when action button is clicked', async () => {
    const onViewProvenance = vi.fn()
    render(<AuditEventTable events={mockEvents} onViewProvenance={onViewProvenance} />)

    const buttons = screen.getAllByRole('button', { name: /View Provenance/i })
    await userEvent.click(buttons[0])

    expect(onViewProvenance).toHaveBeenCalledWith('approved_actual', 'act-uuid-1')
  })
})
