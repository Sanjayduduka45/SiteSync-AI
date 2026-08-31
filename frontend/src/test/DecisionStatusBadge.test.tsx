/**
 * Tests for DecisionStatusBadge component.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DecisionStatusBadge } from '@/features/decisions/components/DecisionStatusBadge'
import type { PlannerDecisionResponse } from '@/features/decisions/types'

describe('DecisionStatusBadge', () => {
  const baseApprovedDecision: PlannerDecisionResponse = {
    id: 'dec-1',
    project_id: 'proj-1',
    match_id: 'match-1',
    extraction_id: 'ext-1',
    decision: 'approved',
    decided_by: 'planner-john',
    decided_at: '2026-08-30T14:30:00Z',
    rejection_reason: null,
    original_payload: {},
    modified_payload: null,
    created_at: '2026-08-30T14:30:00Z',
  }

  it('renders approved status badge and decider identity', () => {
    render(<DecisionStatusBadge decision={baseApprovedDecision} />)
    expect(screen.getByText('Approved')).toBeInTheDocument()
    expect(screen.getByText('planner-john')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /decision status: approved/i })).toBeInTheDocument()
  })

  it('renders rejected status badge with mandatory reason', () => {
    const rejectedDecision: PlannerDecisionResponse = {
      ...baseApprovedDecision,
      decision: 'rejected',
      decided_by: 'planner-sarah',
      rejection_reason: 'Work completed under different sub-contract',
    }
    render(<DecisionStatusBadge decision={rejectedDecision} />)
    expect(screen.getByText('Rejected')).toBeInTheDocument()
    expect(screen.getByText('planner-sarah')).toBeInTheDocument()
    expect(screen.getByText(/"Work completed under different sub-contract"/i)).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /decision status: rejected/i })).toBeInTheDocument()
  })

  it('renders modified status badge with modified values payload', () => {
    const modifiedDecision: PlannerDecisionResponse = {
      ...baseApprovedDecision,
      decision: 'modified',
      decided_by: 'admin-alex',
      modified_payload: {
        actual_quantity: 25.5,
        actual_unit: 'spools',
        actual_date: '2026-08-29',
        notes: 'Adjusted down per morning walk measurement',
      },
    }
    render(<DecisionStatusBadge decision={modifiedDecision} />)
    expect(screen.getByText('Modified')).toBeInTheDocument()
    expect(screen.getByText('admin-alex')).toBeInTheDocument()
    expect(screen.getByText(/25.5 spools/i)).toBeInTheDocument()
    expect(screen.getByText('2026-08-29')).toBeInTheDocument()
    expect(screen.getByText(/"Adjusted down per morning walk measurement"/i)).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /decision status: modified/i })).toBeInTheDocument()
  })

  it('handles unexpected decision fallback gracefully', () => {
    const customDecision = {
      ...baseApprovedDecision,
      decision: 'custom_state' as any,
    }
    render(<DecisionStatusBadge decision={customDecision} />)
    expect(screen.getByText('custom_state')).toBeInTheDocument()
  })
})
