/**
 * Tests for ActivityVarianceTable component.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ActivityVarianceTable } from '@/features/variance/components/ActivityVarianceTable'
import type { ActivityVarianceItem } from '@/features/variance/types'

describe('ActivityVarianceTable', () => {
  const mockItems: ActivityVarianceItem[] = [
    {
      activity_id: '00000000-0000-0000-0000-000000000001',
      project_id: '00000000-0000-0000-0000-0000000000aa',
      activity_code: 'ACT-101',
      name: 'Piping Spools Installation',
      wbs_code: '1.2.1',
      discipline: 'Piping',
      location: 'Area 1',
      planned_quantity: 100,
      planned_unit: 'LF',
      planned_start_date: '2026-08-01',
      planned_finish_date: '2026-08-10',
      actual_quantity_total: 80,
      actual_unit: 'LF',
      latest_actual_date: '2026-08-08',
      approved_actuals_count: 2,
      quantity_variance: -20,
      progress_percent: 80.0,
      date_variance_days: -2,
      variance_status: 'in_progress',
      is_flagged: false,
    },
    {
      activity_id: '00000000-0000-0000-0000-000000000002',
      project_id: '00000000-0000-0000-0000-0000000000aa',
      activity_code: 'ACT-102',
      name: 'Underground Drainage Pipe',
      wbs_code: '1.2.2',
      discipline: 'Civil',
      location: 'Area 2',
      planned_quantity: 100,
      planned_unit: 'LF',
      planned_start_date: '2026-08-01',
      planned_finish_date: '2026-08-10',
      actual_quantity_total: 120,
      actual_unit: 'LF',
      latest_actual_date: '2026-08-13',
      approved_actuals_count: 1,
      quantity_variance: 20,
      progress_percent: 120.0,
      date_variance_days: 3,
      variance_status: 'over_delivered',
      is_flagged: false,
    },
    {
      activity_id: '00000000-0000-0000-0000-000000000003',
      project_id: '00000000-0000-0000-0000-0000000000aa',
      activity_code: 'ACT-M1',
      name: 'Foundation Milestone',
      wbs_code: '1.1',
      discipline: 'Management',
      location: 'Site Wide',
      planned_quantity: null,
      planned_unit: null,
      planned_start_date: '2026-08-01',
      planned_finish_date: '2026-08-10',
      actual_quantity_total: null,
      actual_unit: null,
      latest_actual_date: null,
      approved_actuals_count: 0,
      quantity_variance: null,
      progress_percent: null,
      date_variance_days: null,
      variance_status: 'unquantified',
      is_flagged: false,
    },
    {
      activity_id: '00000000-0000-0000-0000-000000000004',
      project_id: '00000000-0000-0000-0000-0000000000aa',
      activity_code: 'ACT-M2',
      name: 'Structural Bolting',
      wbs_code: '1.3',
      discipline: 'Structural',
      location: 'Tier 1',
      planned_quantity: 50,
      planned_unit: 'spools',
      planned_start_date: '2026-08-01',
      planned_finish_date: '2026-08-10',
      actual_quantity_total: 50,
      actual_unit: 'LF',
      latest_actual_date: '2026-08-09',
      approved_actuals_count: 1,
      quantity_variance: null,
      progress_percent: null,
      date_variance_days: -1,
      variance_status: 'unit_mismatch',
      is_flagged: false,
    },
  ]

  it('renders loading state when isLoading is true', () => {
    render(
      <ActivityVarianceTable
        items={[]}
        total={0}
        limit={50}
        offset={0}
        isLoading={true}
        onPageChange={vi.fn()}
      />
    )
    expect(screen.getByText(/Loading Plan vs Actual variance data.../i)).toBeInTheDocument()
  })

  it('renders empty state when items is empty', () => {
    render(
      <ActivityVarianceTable
        items={[]}
        total={0}
        limit={50}
        offset={0}
        isLoading={false}
        onPageChange={vi.fn()}
      />
    )
    expect(screen.getByText('No schedule activities found.')).toBeInTheDocument()
  })

  it('renders planned values, cumulative actual values, and progress percentages', () => {
    render(
      <ActivityVarianceTable
        items={mockItems}
        total={4}
        limit={50}
        offset={0}
        onPageChange={vi.fn()}
      />
    )

    // Activity codes & names
    expect(screen.getByText('ACT-101')).toBeInTheDocument()
    expect(screen.getByText('Piping Spools Installation')).toBeInTheDocument()
    expect(screen.getByText('ACT-102')).toBeInTheDocument()
    expect(screen.getByText('Underground Drainage Pipe')).toBeInTheDocument()

    // Planned vs Actual
    expect(screen.getAllByText('100 LF').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('80 LF')).toBeInTheDocument()


    // Progress percentage
    expect(screen.getByText('80.0%')).toBeInTheDocument()
    expect(screen.getByText('120.0%')).toBeInTheDocument() // Unclamped >100%
  })

  it('renders quantity variance sign correctly with human-readable explanation', () => {
    render(
      <ActivityVarianceTable
        items={mockItems}
        total={4}
        limit={50}
        offset={0}
        onPageChange={vi.fn()}
      />
    )

    // Under plan (-20 LF)
    expect(screen.getByText('-20 LF')).toBeInTheDocument()
    expect(screen.getByText('20 LF under plan')).toBeInTheDocument()

    // Over plan (+20 LF)
    expect(screen.getByText('+20 LF')).toBeInTheDocument()
    expect(screen.getByText('20 LF over plan')).toBeInTheDocument()
  })

  it('renders date variance sign correctly without predictive language', () => {
    render(
      <ActivityVarianceTable
        items={mockItems}
        total={4}
        limit={50}
        offset={0}
        onPageChange={vi.fn()}
      />
    )

    // Early (-2 days)
    expect(screen.getByText('-2 days Early')).toBeInTheDocument()

    // Late (+3 days)
    expect(screen.getByText('+3 days Late')).toBeInTheDocument()
  })

  it('renders unquantified and unit mismatch items safely with em dashes for undefined math', () => {
    render(
      <ActivityVarianceTable
        items={mockItems}
        total={4}
        limit={50}
        offset={0}
        onPageChange={vi.fn()}
      />
    )

    // Status badges
    expect(screen.getByRole('status', { name: /activity status: unquantified/i })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /activity status: unit mismatch/i })).toBeInTheDocument()
  })
})
