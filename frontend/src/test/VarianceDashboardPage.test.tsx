/**
 * Tests for VarianceDashboardPage component and Phase 9 boundary static inspection.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import VarianceDashboardPage from '@/pages/VarianceDashboardPage'
import * as varianceApi from '@/features/variance/api'
import * as projectContext from '@/features/projects/useProject'

vi.mock('@/features/variance/api')
vi.mock('@/features/projects/useProject')

describe('VarianceDashboardPage', () => {
  let queryClient: QueryClient

  const mockSummary = {
    project_id: '00000000-0000-0000-0000-000000000001',
    total_activities: 2,
    activities_with_progress: 1,
    completed_activities: 0,
    in_progress_activities: 1,
    not_started_activities: 1,
    over_delivered_activities: 0,
    unquantified_activities: 0,
    unit_mismatch_activities: 0,
    flagged_variance_count: 0,
    overall_progress_percent: 50.0,
    unit_rollups: [
      {
        unit: 'LF',
        planned_total: 200,
        actual_total: 100,
        quantity_variance: -100,
        progress_percent: 50.0,
        activity_count: 2,
      },
    ],
  }

  const mockActivities = {
    items: [
      {
        activity_id: 'act-1',
        project_id: '00000000-0000-0000-0000-000000000001',
        activity_code: 'ACT-001',
        name: 'Excavate Trench',
        wbs_code: '1.1',
        discipline: 'Civil',
        planned_quantity: 100,
        planned_unit: 'LF',
        actual_quantity_total: 100,
        actual_unit: 'LF',
        planned_finish_date: '2026-08-10',
        latest_actual_date: '2026-08-08',
        approved_actuals_count: 1,
        quantity_variance: 0,
        progress_percent: 100.0,
        date_variance_days: -2,
        variance_status: 'completed' as const,
        is_flagged: false,
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  }

  const mockWbs = {
    items: [
      {
        wbs_code: '1.1',
        unit_rollups: [
          {
            unit: 'LF',
            planned_total: 100,
            actual_total: 100,
            quantity_variance: 0,
            progress_percent: 100.0,
            activity_count: 1,
          },
        ],
        unquantified_activity_count: 0,
        unit_mismatch_activity_count: 0,
        total_activity_count: 1,
      },
    ],
    total: 1,
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    vi.clearAllMocks()

    vi.spyOn(projectContext, 'useProject').mockReturnValue({
      projects: [
        {
          projectId: '00000000-0000-0000-0000-000000000001',
          projectName: 'Project Alpha',
          projectCode: 'ALPHA',
          role: 'planner',
        },
      ],
      selectedProject: {
        projectId: '00000000-0000-0000-0000-000000000001',
        projectName: 'Project Alpha',
        projectCode: 'ALPHA',
        role: 'planner',
      },
      selectedProjectId: '00000000-0000-0000-0000-000000000001',
      currentRole: 'planner',
      loadingProjects: false,
      selectProject: vi.fn(),
    })


    vi.mocked(varianceApi.getVarianceSummary).mockResolvedValue(mockSummary)
    vi.mocked(varianceApi.getVarianceActivities).mockResolvedValue(mockActivities)
    vi.mocked(varianceApi.getVarianceWbs).mockResolvedValue(mockWbs)
    vi.mocked(varianceApi.formatVarianceError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Error loading variance'
    )
  })

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <VarianceDashboardPage />
      </QueryClientProvider>
    )

  it('renders page header, summary cards, and activity table on load', async () => {
    renderComponent()

    expect(screen.getByText('Plan vs Actual')).toBeInTheDocument()
    expect(
      screen.getByText(/Human-verified construction progress intelligence/i)
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
      expect(screen.getByText('Excavate Trench')).toBeInTheDocument()
    })
  })

  it('handles filtering and resets pagination offset', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
    })

    const wbsInput = screen.getByLabelText(/WBS Code/i)
    await userEvent.type(wbsInput, '1.2')

    await waitFor(() => {
      expect(varianceApi.getVarianceActivities).toHaveBeenCalledWith(
        '00000000-0000-0000-0000-000000000001',
        expect.objectContaining({ wbs_code: '1.2', offset: 0 })
      )
    })
  })

  it('shows validation error when from_date > to_date and prevents invalid queries', async () => {
    renderComponent()

    const fromDate = screen.getByLabelText(/From Actual Date/i)
    const toDate = screen.getByLabelText(/To Actual Date/i)

    await userEvent.type(fromDate, '2026-08-20')
    await userEvent.type(toDate, '2026-08-10')

    expect(
      screen.getByText('From date must be on or before To date.')
    ).toBeInTheDocument()
  })

  it('clears filters when Clear Filters button is clicked', async () => {
    renderComponent()

    const disciplineInput = screen.getByLabelText(/Discipline/i)
    await userEvent.type(disciplineInput, 'Civil')

    const clearBtn = await screen.findByRole('button', { name: /Clear Filters/i })
    await userEvent.click(clearBtn)

    expect(disciplineInput).toHaveValue('')
  })

  it('renders sanitized error message when summary or activity query fails', async () => {
    vi.mocked(varianceApi.getVarianceActivities).mockRejectedValue(
      new Error('API error: 403 Forbidden')
    )
    vi.mocked(varianceApi.formatVarianceError).mockReturnValue(
      "You don't have permission to view project variance."
    )

    renderComponent()

    await waitFor(() => {
      expect(
        screen.getByText("You don't have permission to view project variance.")
      ).toBeInTheDocument()
    })
  })

  it('statically scans Phase 8.3 frontend runtime files to guarantee zero Phase 9 concepts', () => {
    const rawFiles = import.meta.glob<string>(
      ['../features/variance/**/*.ts', '../features/variance/**/*.tsx', '../pages/VarianceDashboardPage.tsx'],
      { query: '?raw', import: 'default', eager: true }
    )

    const forbiddenTokens = [
      'critical_path',
      'total_float',
      'free_float',
      'slack_days',
      'delay_prediction',
      'forecast',
      'risk_score',
      'risk_level',
      'risk_heatmap',
      'downstream_impact',
    ]

    for (const [filePath, content] of Object.entries(rawFiles)) {
      const lower = content.toLowerCase()
      for (const token of forbiddenTokens) {
        expect(
          lower.includes(token),
          `Found forbidden Phase 9 concept "${token}" in file: ${filePath}`
        ).toBe(false)
      }
    }
  })
})
