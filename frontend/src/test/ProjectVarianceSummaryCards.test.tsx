/**
 * Tests for ProjectVarianceSummaryCards component.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ProjectVarianceSummaryCards } from '@/features/variance/components/ProjectVarianceSummaryCards'
import type { ProjectVarianceSummary } from '@/features/variance/types'

describe('ProjectVarianceSummaryCards', () => {
  const homogeneousSummary: ProjectVarianceSummary = {
    project_id: '00000000-0000-0000-0000-000000000001',
    total_activities: 10,
    activities_with_progress: 6,
    completed_activities: 3,
    in_progress_activities: 3,
    not_started_activities: 4,
    over_delivered_activities: 0,
    unquantified_activities: 0,
    unit_mismatch_activities: 0,
    flagged_variance_count: 0,
    overall_progress_percent: 55.0,
    unit_rollups: [
      {
        unit: 'LF',
        planned_total: 1000,
        actual_total: 550,
        quantity_variance: -450,
        progress_percent: 55.0,
        activity_count: 10,
      },
    ],
  }

  const multiUnitSummary: ProjectVarianceSummary = {
    project_id: '00000000-0000-0000-0000-000000000001',
    total_activities: 15,
    activities_with_progress: 8,
    completed_activities: 4,
    in_progress_activities: 4,
    not_started_activities: 7,
    over_delivered_activities: 1,
    unquantified_activities: 1,
    unit_mismatch_activities: 0,
    flagged_variance_count: 2,
    overall_progress_percent: null,
    unit_rollups: [
      {
        unit: 'LF',
        planned_total: 1000,
        actual_total: 550,
        quantity_variance: -450,
        progress_percent: 55.0,
        activity_count: 10,
      },
      {
        unit: 'tons',
        planned_total: 200,
        actual_total: 125,
        quantity_variance: -75,
        progress_percent: 62.5,
        activity_count: 5,
      },
    ],
  }

  it('renders total activities and status breakdown counts accurately', () => {
    render(<ProjectVarianceSummaryCards summary={homogeneousSummary} />)

    expect(screen.getByText('10')).toBeInTheDocument() // Total Activities
    expect(screen.getByText('6')).toBeInTheDocument() // With Verified Progress
    expect(screen.getAllByText('3').length).toBe(2) // Completed & In Progress
    expect(screen.getByText('4')).toBeInTheDocument() // Not Started
  })


  it('renders overall progress percentage when provided by backend for single unit', () => {
    render(<ProjectVarianceSummaryCards summary={homogeneousSummary} />)
    const matches = screen.getAllByText('55.0%')
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })

  it('renders "Multiple units" when overall_progress_percent is null and multiple unit rollups exist', () => {
    render(<ProjectVarianceSummaryCards summary={multiUnitSummary} />)
    expect(screen.getByText('Multiple units')).toBeInTheDocument()
    // Must NOT compute an unweighted average (55 + 62.5)/2 = 58.75%
    expect(screen.queryByText('58.8%')).not.toBeInTheDocument()
    expect(screen.queryByText('58.75%')).not.toBeInTheDocument()
  })

  it('renders unit rollups breakdown clearly with planned, actual, variance and progress', () => {
    render(<ProjectVarianceSummaryCards summary={multiUnitSummary} />)

    expect(screen.getByText('Physical Scope Rollups by Unit')).toBeInTheDocument()
    expect(screen.getByText('LF')).toBeInTheDocument()
    expect(screen.getByText('tons')).toBeInTheDocument()

    expect(screen.getByText('Planned: 1,000 LF')).toBeInTheDocument()
    expect(screen.getByText('Actual: 550 LF')).toBeInTheDocument()
    expect(screen.getByText('Planned: 200 tons')).toBeInTheDocument()
    expect(screen.getByText('Actual: 125 tons')).toBeInTheDocument()
  })

  it('renders flagged variance alert when flagged_variance_count > 0', () => {
    render(<ProjectVarianceSummaryCards summary={multiUnitSummary} />)
    expect(screen.getByText(/activities flagged with significant variance/i)).toBeInTheDocument()
  })

})
