/**
 * Tests for WbsRollupTable component.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { WbsRollupTable } from '@/features/variance/components/WbsRollupTable'
import type { WbsRollup } from '@/features/variance/types'

describe('WbsRollupTable', () => {
  const mockWbs: WbsRollup[] = [
    {
      wbs_code: '1.2',
      unit_rollups: [
        {
          unit: 'LF',
          planned_total: 1000,
          actual_total: 550,
          quantity_variance: -450,
          progress_percent: 55.0,
          activity_count: 5,
        },
        {
          unit: 'tons',
          planned_total: 200,
          actual_total: 250,
          quantity_variance: 50,
          progress_percent: 125.0,
          activity_count: 3,
        },
      ],
      unquantified_activity_count: 0,
      unit_mismatch_activity_count: 0,
      total_activity_count: 8,
    },
    {
      wbs_code: '1.3',
      unit_rollups: [],
      unquantified_activity_count: 2,
      unit_mismatch_activity_count: 0,
      total_activity_count: 2,
    },
  ]

  it('renders WBS rows and separates mixed physical units into distinct rows', () => {
    render(<WbsRollupTable wbsItems={mockWbs} />)

    expect(screen.getByText('1.2')).toBeInTheDocument()
    expect(screen.getByText('1.2 (cont.)')).toBeInTheDocument()

    // Units
    expect(screen.getByText('LF')).toBeInTheDocument()
    expect(screen.getByText('tons')).toBeInTheDocument()

    // Totals & variances
    expect(screen.getByText('1,000 LF')).toBeInTheDocument()
    expect(screen.getByText('550 LF')).toBeInTheDocument()
    expect(screen.getByText('-450 LF')).toBeInTheDocument()
    expect(screen.getByText('55.0%')).toBeInTheDocument()

    expect(screen.getByText('200 tons')).toBeInTheDocument()
    expect(screen.getByText('250 tons')).toBeInTheDocument()
    expect(screen.getByText('+50 tons')).toBeInTheDocument()
    expect(screen.getByText('125.0%')).toBeInTheDocument()
  })

  it('does not combine incompatible physical units or compute an unweighted average', () => {
    render(<WbsRollupTable wbsItems={mockWbs} />)

    // Must NOT combine 1000 LF + 200 tons = 1200 units
    expect(screen.queryByText(/1,200/i)).not.toBeInTheDocument()
    // Must NOT average (55% + 125%)/2 = 90%
    expect(screen.queryByText('90.0%')).not.toBeInTheDocument()
  })

  it('handles unquantified WBS tiers cleanly', () => {
    render(<WbsRollupTable wbsItems={mockWbs} />)

    expect(screen.getByText('1.3')).toBeInTheDocument()
    expect(screen.getByText('2 (Unquantified)')).toBeInTheDocument()
  })
})
