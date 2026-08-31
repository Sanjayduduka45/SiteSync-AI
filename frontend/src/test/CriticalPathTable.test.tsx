/**
 * Tests for CriticalPathTable component — SiteSync AI Phase 9.6.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { CriticalPathTable } from '@/features/risk/components/CriticalPathTable'
import type { CPMActivityNodeResponse } from '@/features/risk/types'

describe('CriticalPathTable', () => {
  const mockActivities: CPMActivityNodeResponse[] = [
    {
      activity_id: 'act-1',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-101',
      name: 'Site Grading',
      wbs_code: '1.1',
      discipline: 'Civil',
      location: 'Site',
      planned_start_date: '2026-09-01',
      planned_finish_date: '2026-09-05',
      duration_days: 5,
      early_start: '2026-09-01',
      early_finish: '2026-09-05',
      late_start: '2026-09-01',
      late_finish: '2026-09-05',
      total_float_days: 0,
      free_float_days: 0,
      is_critical: true,
    },
    {
      activity_id: 'act-2',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-102',
      name: 'Fencing',
      wbs_code: '1.2',
      discipline: 'Security',
      location: 'Perimeter',
      planned_start_date: '2026-09-01',
      planned_finish_date: '2026-09-03',
      duration_days: 3,
      early_start: '2026-09-01',
      early_finish: '2026-09-03',
      late_start: '2026-09-04',
      late_finish: '2026-09-06',
      total_float_days: 3,
      free_float_days: 3,
      is_critical: false,
    },
    {
      activity_id: 'act-3',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-103',
      name: 'Late Excavation',
      wbs_code: '1.3',
      discipline: 'Civil',
      location: 'Pit',
      planned_start_date: '2026-09-05',
      planned_finish_date: '2026-09-10',
      duration_days: 6,
      early_start: '2026-09-07',
      early_finish: '2026-09-12',
      late_start: '2026-09-05',
      late_finish: '2026-09-10',
      total_float_days: -2,
      free_float_days: 0,
      is_critical: true,
    },
  ]

  it('renders all CPM schedule activities and header totals', () => {
    render(
      <CriticalPathTable
        activities={mockActivities}
        totalActivities={3}
        criticalCount={2}
      />
    )

    expect(screen.getByText('ACT-101')).toBeInTheDocument()
    expect(screen.getByText('Site Grading')).toBeInTheDocument()
    expect(screen.getByText('ACT-102')).toBeInTheDocument()
    expect(screen.getByText('Fencing')).toBeInTheDocument()
    expect(screen.getByText('ACT-103')).toBeInTheDocument()
    expect(screen.getByText('Late Excavation')).toBeInTheDocument()

    expect(screen.getByText('Critical: 2')).toBeInTheDocument()
  })

  it('preserves exact numeric float values including negative float', () => {
    render(
      <CriticalPathTable
        activities={mockActivities}
        totalActivities={3}
        criticalCount={2}
      />
    )

    expect(screen.getAllByText('0d').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('3d').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('-2d')).toBeInTheDocument() // Non-clamped negative float

  })

  it('displays explicit CRITICAL status badges for critical activities', () => {
    render(
      <CriticalPathTable
        activities={mockActivities}
        totalActivities={3}
        criticalCount={2}
      />
    )

    const critBadges = screen.getAllByRole('status')
    expect(critBadges.length).toBe(3)
    expect(screen.getAllByText('CRITICAL').length).toBe(2)
    expect(screen.getByText('Non-Critical')).toBeInTheDocument()
  })

  it('renders loading skeleton when isLoading is true', () => {
    render(<CriticalPathTable isLoading={true} />)
    expect(screen.getByTestId('cpm-table-loading')).toBeInTheDocument()
  })

  it('renders empty message when activities array is empty', () => {
    render(<CriticalPathTable activities={[]} />)
    expect(screen.getByText('No Critical Path schedule data found.')).toBeInTheDocument()
  })
})
