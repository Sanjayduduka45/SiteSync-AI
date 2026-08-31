/**
 * Tests for VarianceStatusBadge component.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { VarianceStatusBadge } from '@/features/variance/components/VarianceStatusBadge'

describe('VarianceStatusBadge', () => {
  it('renders all six canonical variance statuses correctly with accessible aria-labels', () => {
    const { rerender } = render(<VarianceStatusBadge status="not_started" />)
    expect(screen.getByRole('status', { name: /activity status: not started/i })).toHaveTextContent(
      'Not Started'
    )

    rerender(<VarianceStatusBadge status="in_progress" />)
    expect(screen.getByRole('status', { name: /activity status: in progress/i })).toHaveTextContent(
      'In Progress'
    )

    rerender(<VarianceStatusBadge status="completed" />)
    expect(screen.getByRole('status', { name: /activity status: completed/i })).toHaveTextContent(
      'Completed'
    )

    rerender(<VarianceStatusBadge status="over_delivered" />)
    expect(screen.getByRole('status', { name: /activity status: over delivered/i })).toHaveTextContent(
      'Over Delivered'
    )

    rerender(<VarianceStatusBadge status="unquantified" />)
    expect(screen.getByRole('status', { name: /activity status: unquantified/i })).toHaveTextContent(
      'Unquantified'
    )

    rerender(<VarianceStatusBadge status="unit_mismatch" />)
    expect(screen.getByRole('status', { name: /activity status: unit mismatch/i })).toHaveTextContent(
      'Unit Mismatch'
    )
  })

  it('contains zero forbidden Phase 9 risk or predictive terminology in rendered output', () => {
    const statuses = [
      'not_started',
      'in_progress',
      'completed',
      'over_delivered',
      'unquantified',
      'unit_mismatch',
    ] as const

    for (const status of statuses) {
      const { container } = render(<VarianceStatusBadge status={status} />)
      const text = container.textContent?.toLowerCase() || ''
      expect(text).not.toContain('risk')
      expect(text).not.toContain('critical')
      expect(text).not.toContain('delay')
      expect(text).not.toContain('forecast')
      expect(text).not.toContain('predict')
    }
  })
})
