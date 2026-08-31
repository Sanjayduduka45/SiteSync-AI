/**
 * Tests for RiskHeatmap component — SiteSync AI Phase 9.6.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { RiskHeatmap } from '@/features/risk/components/RiskHeatmap'
import type { ActivityRiskAssessment } from '@/features/risk/types'

describe('RiskHeatmap', () => {
  const mockActivities: ActivityRiskAssessment[] = [
    {
      activity_id: 'act-1',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-001',
      name: 'Foundation Pour',
      wbs_code: '1.1',
      discipline: 'Civil',
      location: 'Sector A',
      severity: 'critical',
      risk_score: 85,
      categories: ['critical_path_delay'],
      is_critical_path: true,
      total_float: 0,
      date_variance_days: 5,
      direct_successors_count: 2,
      transitive_successors_count: 5,
      critical_slippage_successors_count: 3,
      variance_status: 'in_progress',
      progress_percent: 40.0,
      is_completed: false,
    },
    {
      activity_id: 'act-2',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-002',
      name: 'Piping Install',
      wbs_code: '1.2',
      discipline: 'Piping',
      location: 'Sector B',
      severity: 'high',
      risk_score: 65,
      categories: ['float_erosion'],
      is_critical_path: false,
      total_float: 2,
      date_variance_days: 3,
      direct_successors_count: 1,
      transitive_successors_count: 2,
      critical_slippage_successors_count: 1,
      variance_status: 'in_progress',
      progress_percent: 20.0,
      is_completed: false,
    },
    {
      activity_id: 'act-3',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-003',
      name: 'Cable Pulling',
      wbs_code: '1.3',
      discipline: 'Electrical',
      location: 'Sector C',
      severity: 'low',
      risk_score: 15,
      categories: [],
      is_critical_path: false,
      total_float: 12,
      date_variance_days: 0,
      direct_successors_count: 0,
      transitive_successors_count: 0,
      critical_slippage_successors_count: 0,
      variance_status: 'not_started',
      progress_percent: 0.0,
      is_completed: false,
    },
  ]

  it('renders discipline rows and float bands header accurately', () => {
    render(<RiskHeatmap activities={mockActivities} />)

    expect(screen.getByText('Discipline \\ Float Band')).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Near-Critical')).toBeInTheDocument()
    expect(screen.getByText('Moderate')).toBeInTheDocument()
    expect(screen.getByText('Safe')).toBeInTheDocument()

    expect(screen.getByText('Civil')).toBeInTheDocument()
    expect(screen.getByText('Piping')).toBeInTheDocument()
    expect(screen.getByText('Electrical')).toBeInTheDocument()
  })

  it('displays accurate activity count per discipline and severity cell', () => {
    render(<RiskHeatmap activities={mockActivities} />)

    // Civil -> Critical should have count 1
    const civilCritCell = screen.getByLabelText('1 Critical activities in Civil')
    expect(civilCritCell).toBeInTheDocument()

    // Piping -> Near-Critical should have count 1
    const pipingHighCell = screen.getByLabelText('1 Near-Critical activities in Piping')
    expect(pipingHighCell).toBeInTheDocument()
  })

  it('invokes onSelectCell callback when a matrix cell is clicked', async () => {
    const onSelectCell = vi.fn()
    render(<RiskHeatmap activities={mockActivities} onSelectCell={onSelectCell} />)

    const civilCritCell = screen.getByLabelText('1 Critical activities in Civil')
    await userEvent.click(civilCritCell)

    expect(onSelectCell).toHaveBeenCalledWith('critical', 'Civil')
  })

  it('renders loading skeleton when isLoading is true', () => {
    render(<RiskHeatmap isLoading={true} />)
    expect(screen.getByTestId('risk-heatmap-loading')).toBeInTheDocument()
  })

  it('renders empty message when no activities are provided', () => {
    render(<RiskHeatmap activities={[]} />)
    expect(screen.getByText('No activity data available to generate heatmap matrix.')).toBeInTheDocument()
  })
})
