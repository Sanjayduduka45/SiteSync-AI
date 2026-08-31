/**
 * Tests for DownstreamImpactDrawer component — SiteSync AI Phase 9.6.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DownstreamImpactDrawer } from '@/features/risk/components/DownstreamImpactDrawer'
import * as riskApi from '@/features/risk/api'
import type { DownstreamImpactResult } from '@/features/risk/types'

vi.mock('@/features/risk/api')

describe('DownstreamImpactDrawer', () => {
  let queryClient: QueryClient

  const mockImpactResult: DownstreamImpactResult = {
    project_id: '00000000-0000-0000-0000-000000000001',
    source_activity_id: 'act-source',
    source_activity_code: 'ACT-100',
    source_name: 'Excavate Foundation',
    source_delay_days: 4,
    is_source_critical: true,
    total_downstream_activities_count: 2,
    critical_slippage_count: 1,
    buffer_absorbed_count: 1,
    historical_completed_count: 0,
    impacted_successors: [
      {
        activity_id: 'succ-1',
        activity_code: 'ACT-101',
        name: 'Formwork',
        wbs_code: '1.1',
        discipline: 'Civil',
        depth: 1,
        path: ['ACT-100', 'ACT-101'],
        relationship_with_immediate_predecessor: 'FS',
        lag_days_with_immediate_predecessor: 0,
        planned_start_date: '2026-09-01',
        planned_finish_date: '2026-09-05',
        total_float: 0,
        free_float: 0,
        is_critical: true,
        is_completed: false,
        impact_severity: 'critical_slippage',
        available_float: 0,
        float_consumed: 0,
        projected_delay_days: 4,
      },
      {
        activity_id: 'succ-2',
        activity_code: 'ACT-102',
        name: 'Site Cleanup',
        wbs_code: '1.2',
        discipline: 'General',
        depth: 2,
        path: ['ACT-100', 'ACT-101', 'ACT-102'],
        relationship_with_immediate_predecessor: 'FS',
        lag_days_with_immediate_predecessor: 1,
        planned_start_date: '2026-09-06',
        planned_finish_date: '2026-09-08',
        total_float: 5,
        free_float: 5,
        is_critical: false,
        is_completed: false,
        impact_severity: 'buffer_absorbed',
        available_float: 5,
        float_consumed: 4,
        projected_delay_days: 0,
      },
    ],
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    vi.clearAllMocks()
    vi.mocked(riskApi.getDownstreamImpact).mockResolvedValue(mockImpactResult)
    vi.mocked(riskApi.formatRiskError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Error'
    )
  })

  const renderComponent = (isOpen = true) =>
    render(
      <QueryClientProvider client={queryClient}>
        <DownstreamImpactDrawer
          projectId="00000000-0000-0000-0000-000000000001"
          activityId="act-source"
          isOpen={isOpen}
          onClose={vi.fn()}
        />
      </QueryClientProvider>
    )

  it('renders source activity summary and impacted successor graph when open', async () => {
    renderComponent(true)

    await waitFor(() => {
      expect(screen.getByText(/Excavate Foundation/i)).toBeInTheDocument()
      expect(screen.getAllByText('ACT-101').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Formwork')).toBeInTheDocument()
      expect(screen.getAllByText('Critical Slippage').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('ACT-102').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Buffer Absorbed').length).toBeGreaterThanOrEqual(1)
    })
  })



  it('renders nothing when isOpen is false', () => {
    const { container } = renderComponent(false)
    expect(container.firstChild).toBeNull()
  })

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn()
    render(
      <QueryClientProvider client={queryClient}>
        <DownstreamImpactDrawer
          projectId="00000000-0000-0000-0000-000000000001"
          activityId="act-source"
          isOpen={true}
          onClose={onClose}
        />
      </QueryClientProvider>
    )

    const closeBtn = screen.getByLabelText(/Close drawer/i)
    await userEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })
})
