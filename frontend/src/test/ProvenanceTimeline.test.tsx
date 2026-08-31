import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ProvenanceTimeline } from '@/features/audit/components/ProvenanceTimeline'
import type { ProvenanceChain } from '@/features/audit/types'

describe('ProvenanceTimeline', () => {
  const completeChain: ProvenanceChain = {
    project_id: '00000000-0000-0000-0000-000000000001',
    root_entity_type: 'APPROVED_ACTUAL',
    root_entity_id: 'actual-1',
    nodes: [
      {
        node_id: 'FIELD_INPUT:inp-1',
        node_type: 'FIELD_INPUT',
        entity_id: 'inp-1',
        title: 'Daily Site Log',
        status: 'SUBMITTED',
        timestamp: '2026-08-31T08:00:00Z',
        details: { title: 'Daily Site Log', input_type: 'text' },
      },
      {
        node_id: 'PLANNER_DECISION:dec-1',
        node_type: 'PLANNER_DECISION',
        entity_id: 'dec-1',
        title: 'Planner Review (APPROVED)',
        status: 'APPROVED',
        timestamp: '2026-08-31T09:00:00Z',
        details: { decision: 'approved' },
      },
    ],
    links: [
      {
        source_node_id: 'FIELD_INPUT:inp-1',
        target_node_id: 'PLANNER_DECISION:dec-1',
        relationship: 'COMMITS_TO',
      },
    ],
    is_complete: true,
    unresolved_links: [],
  }

  const incompleteChain: ProvenanceChain = {
    project_id: '00000000-0000-0000-0000-000000000001',
    root_entity_type: 'APPROVED_ACTUAL',
    root_entity_id: 'actual-2',
    nodes: [
      {
        node_id: 'APPROVED_ACTUAL:actual-2',
        node_type: 'APPROVED_ACTUAL',
        entity_id: 'actual-2',
        title: 'Approved Actual: 100 LF',
        status: 'APPROVED',
        timestamp: '2026-08-31T10:00:00Z',
        details: { actual_quantity: 100 },
      },
    ],
    links: [],
    is_complete: false,
    unresolved_links: ['No AI extraction record found for ID "ext-999"'],
  }

  it('renders complete provenance nodes and statuses without warnings', () => {
    render(<ProvenanceTimeline chain={completeChain} />)

    expect(screen.getAllByText('Daily Site Log').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Planner Review (APPROVED)')).toBeInTheDocument()
    expect(screen.queryByText(/Provenance chain is incomplete/i)).not.toBeInTheDocument()
  })

  it('renders incomplete provenance warning and unresolved link messages when is_complete is false', () => {
    render(<ProvenanceTimeline chain={incompleteChain} />)

    expect(screen.getByText(/Provenance chain is incomplete/i)).toBeInTheDocument()
    expect(
      screen.getByText('No AI extraction record found for ID "ext-999"')
    ).toBeInTheDocument()
  })
})
