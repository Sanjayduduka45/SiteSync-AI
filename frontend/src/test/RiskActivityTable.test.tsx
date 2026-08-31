/**
 * Tests for RiskActivityTable component — SiteSync AI Phase 9.6.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { RiskActivityTable } from '@/features/risk/components/RiskActivityTable'
import type { ActivityRiskAssessment } from '@/features/risk/types'

describe('RiskActivityTable', () => {
  const mockItems: ActivityRiskAssessment[] = [
    {
      activity_id: 'act-101',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-101',
      name: 'Pour Foundation Slab',
      wbs_code: '1.1.2',
      discipline: 'Civil',
      location: 'Building A',
      severity: 'critical',
      risk_score: 92,
      categories: ['critical_path_delay', 'downstream_bottleneck'],
      is_critical_path: true,
      total_float: 0,
      date_variance_days: 6,
      direct_successors_count: 3,
      transitive_successors_count: 8,
      critical_slippage_successors_count: 5,
      variance_status: 'in_progress',
      progress_percent: 35.0,
      is_completed: false,
    },
    {
      activity_id: 'act-102',
      project_id: '00000000-0000-0000-0000-000000000001',
      activity_code: 'ACT-102',
      name: 'Erect Structural Steel',
      wbs_code: '1.2.1',
      discipline: 'Structural',
      location: 'Building A',
      severity: 'high',
      risk_score: 68,
      categories: ['float_erosion'],
      is_critical_path: false,
      total_float: 2,
      date_variance_days: 2,
      direct_successors_count: 2,
      transitive_successors_count: 4,
      critical_slippage_successors_count: 2,
      variance_status: 'not_started',
      progress_percent: 0.0,
      is_completed: false,
    },
  ]

  it('renders activity rows with codes, names, scores, and canonical categories', () => {
    const onPageChange = vi.fn()
    const onViewImpact = vi.fn()

    render(
      <RiskActivityTable
        items={mockItems}
        total={2}
        limit={50}
        offset={0}
        onPageChange={onPageChange}
        onViewImpact={onViewImpact}
      />
    )

    expect(screen.getByText('ACT-101')).toBeInTheDocument()
    expect(screen.getByText('Pour Foundation Slab')).toBeInTheDocument()
    expect(screen.getByText('92')).toBeInTheDocument()
    expect(screen.getByText('Critical Path Delay')).toBeInTheDocument()
    expect(screen.getByText('Downstream Bottleneck')).toBeInTheDocument()

    expect(screen.getByText('ACT-102')).toBeInTheDocument()
    expect(screen.getByText('Erect Structural Steel')).toBeInTheDocument()
    expect(screen.getByText('68')).toBeInTheDocument()
    expect(screen.getByText('Float Erosion')).toBeInTheDocument()
  })

  it('invokes onViewImpact callback with activity ID when View Impact button is clicked', async () => {
    const onPageChange = vi.fn()
    const onViewImpact = vi.fn()

    render(
      <RiskActivityTable
        items={mockItems}
        total={2}
        limit={50}
        offset={0}
        onPageChange={onPageChange}
        onViewImpact={onViewImpact}
      />
    )

    const viewImpactButtons = screen.getAllByRole('button', { name: /View Impact/i })
    expect(viewImpactButtons.length).toBe(2)

    await userEvent.click(viewImpactButtons[0])
    expect(onViewImpact).toHaveBeenCalledWith('act-101')
  })

  it('handles pagination next and previous clicks', async () => {
    const onPageChange = vi.fn()
    const onViewImpact = vi.fn()

    render(
      <RiskActivityTable
        items={mockItems}
        total={100}
        limit={50}
        offset={0}
        onPageChange={onPageChange}
        onViewImpact={onViewImpact}
      />
    )

    const nextButton = screen.getByRole('button', { name: /Next/i })
    expect(nextButton).not.toBeDisabled()

    await userEvent.click(nextButton)
    expect(onPageChange).toHaveBeenCalledWith(50)
  })

  it('renders loading state when isLoading is true', () => {
    render(
      <RiskActivityTable
        items={[]}
        total={0}
        limit={50}
        offset={0}
        isLoading={true}
        onPageChange={vi.fn()}
        onViewImpact={vi.fn()}
      />
    )
    expect(screen.getByTestId('risk-table-loading')).toBeInTheDocument()
  })

  it('renders empty state when items list is empty', () => {
    render(
      <RiskActivityTable
        items={[]}
        total={0}
        limit={50}
        offset={0}
        isLoading={false}
        onPageChange={vi.fn()}
        onViewImpact={vi.fn()}
      />
    )
    expect(screen.getByText('No activity risk records found.')).toBeInTheDocument()
  })
})
