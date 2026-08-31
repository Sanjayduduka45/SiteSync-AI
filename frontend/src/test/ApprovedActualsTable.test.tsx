/**
 * Tests for ApprovedActualsTable component.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import { ApprovedActualsTable } from '@/features/decisions/components/ApprovedActualsTable'
import type { ApprovedActualResponse } from '@/features/decisions/types'
import type { ScheduleActivity } from '@/features/schedules/types'

describe('ApprovedActualsTable', () => {
  const mockActivities: Record<string, ScheduleActivity> = {
    'act-1': {
      id: 'act-1',
      project_id: 'proj-1',
      activity_code: 'ACT-101',
      name: 'Erect Steel Tier 1',
      discipline: 'Civil',
      created_at: '2026-08-30T12:00:00Z',
      updated_at: '2026-08-30T12:00:00Z',
    },
    'act-2': {
      id: 'act-2',
      project_id: 'proj-1',
      activity_code: 'ACT-202',
      name: 'Underground Sewer Pipe',
      discipline: 'Piping',
      created_at: '2026-08-30T12:00:00Z',
      updated_at: '2026-08-30T12:00:00Z',
    },
  }

  const mockItems: ApprovedActualResponse[] = [
    {
      id: 'actual-1',
      project_id: 'proj-1',
      schedule_activity_id: 'act-1',
      extraction_id: 'ext-1',
      match_id: 'match-1',
      activity_index: 0,
      actual_quantity: 15.5,
      actual_unit: 'tons',
      actual_date: '2026-08-30',
      source_evidence: ['erected 15.5 tons', 'Grid 4'],
      approved_by: 'planner-john',
      approved_at: '2026-08-30T14:00:00Z',
      notes: 'Verified against morning site walk',
      is_modified: false,
      created_at: '2026-08-30T14:00:00Z',
      updated_at: '2026-08-30T14:00:00Z',
    },
    {
      id: 'actual-2',
      project_id: 'proj-1',
      schedule_activity_id: 'act-2',
      extraction_id: 'ext-1',
      match_id: 'match-2',
      activity_index: 1,
      actual_quantity: 20,
      actual_unit: 'LF',
      actual_date: '2026-08-29',
      source_evidence: [{ token: 'laid 20 LF' }, { token: 'Trench 2' }],
      approved_by: 'admin-sarah',
      approved_at: '2026-08-30T15:00:00Z',
      notes: 'Quantity adjusted down from 25 to 20 LF per pipe foreman count',
      is_modified: true,
      created_at: '2026-08-30T15:00:00Z',
      updated_at: '2026-08-30T15:00:00Z',
    },
  ]

  it('renders loading state when isLoading is true', () => {
    render(<ApprovedActualsTable items={[]} isLoading={true} />)
    expect(screen.getByText(/Loading approved actuals…/i)).toBeInTheDocument()
  })

  it('renders empty state when items is empty', () => {
    render(<ApprovedActualsTable items={[]} isLoading={false} />)
    expect(screen.getByText('No approved actuals yet.')).toBeInTheDocument()
    expect(
      screen.getByText(/Approved progress will appear here after a Planner or Admin reviews an AI recommendation\./i)
    ).toBeInTheDocument()
  })

  it('renders table headers and row data correctly', () => {
    render(<ApprovedActualsTable items={mockItems} activitiesMap={mockActivities} />)

    // Activity codes & names
    expect(screen.getByText('ACT-101')).toBeInTheDocument()
    expect(screen.getByText('Erect Steel Tier 1')).toBeInTheDocument()
    expect(screen.getByText('ACT-202')).toBeInTheDocument()
    expect(screen.getByText('Underground Sewer Pipe')).toBeInTheDocument()

    // Quantities & units
    expect(screen.getByText('15.5')).toBeInTheDocument()
    expect(screen.getByText('tons')).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByText('LF')).toBeInTheDocument()

    // Work dates
    expect(screen.getByText('2026-08-30')).toBeInTheDocument()
    expect(screen.getByText('2026-08-29')).toBeInTheDocument()
  })

  it('renders Approved vs Modified & Approved badges accurately', () => {
    render(<ApprovedActualsTable items={mockItems} activitiesMap={mockActivities} />)

    // First item is not modified -> Approved
    expect(screen.getByRole('status', { name: /approval status: approved/i })).toBeInTheDocument()

    // Second item is modified -> Modified & Approved
    expect(
      screen.getByRole('status', { name: /approval status: modified & approved/i })
    ).toBeInTheDocument()
  })

  it('renders decider identity and timestamps safely', () => {
    render(<ApprovedActualsTable items={mockItems} activitiesMap={mockActivities} />)
    expect(screen.getByText('planner-john')).toBeInTheDocument()
    expect(screen.getByText('admin-sarah')).toBeInTheDocument()
  })

  it('expands evidence tokens on button click without exposing raw JSON', async () => {
    render(<ApprovedActualsTable items={mockItems} activitiesMap={mockActivities} />)

    const evidenceBtns = screen.getAllByRole('button', { name: /evidence/i })
    await userEvent.click(evidenceBtns[0])

    // Should display token chips
    expect(screen.getByText('"erected 15.5 tons"')).toBeInTheDocument()
    expect(screen.getByText('"Grid 4"')).toBeInTheDocument()

    // Should not display raw JSON
    expect(screen.queryByText(/\{"token"/i)).not.toBeInTheDocument()
  })

  it('truncates long notes and expands on More click', async () => {
    render(<ApprovedActualsTable items={mockItems} activitiesMap={mockActivities} />)

    const moreBtn = screen.getByRole('button', { name: /more/i })
    expect(moreBtn).toBeInTheDocument()

    await userEvent.click(moreBtn)
    expect(
      screen.getByText(/"Quantity adjusted down from 25 to 20 LF per pipe foreman count"/i)
    ).toBeInTheDocument()
  })
})
