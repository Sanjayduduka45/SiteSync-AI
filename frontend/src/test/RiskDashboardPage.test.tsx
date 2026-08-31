/**
 * Tests for RiskDashboardPage component & Phase 9.6 static boundary inspection.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import RiskDashboardPage from '@/pages/RiskDashboardPage'
import * as riskApi from '@/features/risk/api'
import * as projectContext from '@/features/projects/useProject'

vi.mock('@/features/risk/api')
vi.mock('@/features/projects/useProject')

describe('RiskDashboardPage', () => {
  let queryClient: QueryClient

  const mockSummary = {
    project_id: '00000000-0000-0000-0000-000000000001',
    total_activities: 3,
    critical_severity_count: 1,
    high_severity_count: 1,
    medium_severity_count: 1,
    low_severity_count: 0,
    critical_path_delay_count: 1,
    float_erosion_count: 1,
    downstream_bottleneck_count: 1,
    predecessor_blocker_count: 0,
    unquantified_milestone_lag_count: 0,
    unit_mismatch_exposure_count: 0,
    average_risk_score: 72.5,
    items: [
      {
        activity_id: 'act-1',
        project_id: '00000000-0000-0000-0000-000000000001',
        activity_code: 'ACT-001',
        name: 'Excavate Foundation',
        wbs_code: '1.1',
        discipline: 'Civil',
        location: 'Zone 1',
        severity: 'critical' as const,
        risk_score: 95,
        categories: ['critical_path_delay' as const],
        is_critical_path: true,
        total_float: -1,
        date_variance_days: 4,
        direct_successors_count: 1,
        transitive_successors_count: 2,
        critical_slippage_successors_count: 1,
        variance_status: 'in_progress',
        progress_percent: 50.0,
        is_completed: false,
      },
    ],
  }

  const mockActivities = {
    items: [
      {
        activity_id: 'act-1',
        project_id: '00000000-0000-0000-0000-000000000001',
        activity_code: 'ACT-001',
        name: 'Excavate Foundation',
        wbs_code: '1.1',
        discipline: 'Civil',
        location: 'Zone 1',
        severity: 'critical' as const,
        risk_score: 95,
        categories: ['critical_path_delay' as const],
        is_critical_path: true,
        total_float: -1,
        date_variance_days: 4,
        direct_successors_count: 1,
        transitive_successors_count: 2,
        critical_slippage_successors_count: 1,
        variance_status: 'in_progress',
        progress_percent: 50.0,
        is_completed: false,
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  }

  const mockCpm = {
    project_id: '00000000-0000-0000-0000-000000000001',
    project_start_date: '2026-09-01',
    project_finish_date: '2026-09-30',
    total_activities: 1,
    critical_activities_count: 1,
    critical_path_activity_ids: ['act-1'],
    activities: [
      {
        activity_id: 'act-1',
        project_id: '00000000-0000-0000-0000-000000000001',
        activity_code: 'ACT-001',
        name: 'Excavate Foundation',
        wbs_code: '1.1',
        discipline: 'Civil',
        location: 'Zone 1',
        planned_start_date: '2026-09-01',
        planned_finish_date: '2026-09-10',
        duration_days: 10,
        early_start: '2026-09-01',
        early_finish: '2026-09-10',
        late_start: '2026-08-31',
        late_finish: '2026-09-09',
        total_float_days: -1,
        free_float_days: 0,
        is_critical: true,
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

    vi.mocked(riskApi.getRiskSummary).mockResolvedValue(mockSummary)
    vi.mocked(riskApi.getRiskActivities).mockResolvedValue(mockActivities)
    vi.mocked(riskApi.getCriticalPath).mockResolvedValue(mockCpm)
    vi.mocked(riskApi.getDownstreamImpact).mockResolvedValue({
      project_id: '00000000-0000-0000-0000-000000000001',
      source_activity_id: 'act-1',
      source_activity_code: 'ACT-001',
      source_name: 'Excavate Foundation',
      source_delay_days: 4,
      is_source_critical: true,
      total_downstream_activities_count: 0,
      critical_slippage_count: 0,
      buffer_absorbed_count: 0,
      historical_completed_count: 0,
      impacted_successors: [],
    })
    vi.mocked(riskApi.formatRiskError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Error loading risks'
    )

  })

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <RiskDashboardPage />
      </QueryClientProvider>
    )

  it('renders page header, summary KPI cards, heatmap, and risk register on load', async () => {
    renderComponent()

    expect(screen.getByText('Risk & Critical Path Intelligence')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
      expect(screen.getByText('Excavate Foundation')).toBeInTheDocument()
      expect(screen.getByText('72.5')).toBeInTheDocument() // Average Risk Score
    })
  })

  it('switches to Critical Path tab and renders CPM table with preserved negative float', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
    })

    const cpmTabBtn = screen.getByRole('button', { name: /Critical Path Schedule/i })
    await userEvent.click(cpmTabBtn)

    await waitFor(() => {
      expect(screen.getByText('Critical Path Schedule Network')).toBeInTheDocument()
      expect(screen.getByText('-1d')).toBeInTheDocument() // Non-clamped negative total float
      expect(screen.getAllByText('CRITICAL').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('handles server-side filtering and resets pagination offset', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
    })

    const severitySelect = screen.getByLabelText(/Severity Level/i)
    await userEvent.selectOptions(severitySelect, 'critical')

    await waitFor(() => {
      expect(riskApi.getRiskActivities).toHaveBeenCalledWith(
        '00000000-0000-0000-0000-000000000001',
        expect.objectContaining({ severity: 'critical', offset: 0 })
      )
    })
  })

  it('opens downstream impact drawer when View Impact is clicked', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('ACT-001')).toBeInTheDocument()
    })

    const viewImpactBtn = screen.getByRole('button', { name: /View Impact/i })
    await userEvent.click(viewImpactBtn)

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /Downstream Impact Analysis/i })).toBeInTheDocument()
    })
  })

  it('renders sanitized error message when summary or activity query fails', async () => {
    vi.mocked(riskApi.getRiskActivities).mockRejectedValue(
      new Error('API error: 403 Forbidden')
    )
    vi.mocked(riskApi.formatRiskError).mockReturnValue(
      "You don't have permission to view project risks."
    )

    renderComponent()

    await waitFor(() => {
      expect(
        screen.getByText("You don't have permission to view project risks.")
      ).toBeInTheDocument()
    })
  })

  it('statically scans Phase 9.6 frontend runtime files to guarantee zero client-side calculation engines', () => {
    const rawFiles = import.meta.glob<string>(
      ['../features/risk/**/*.ts', '../features/risk/**/*.tsx', '../pages/RiskDashboardPage.tsx'],
      { query: '?raw', import: 'default', eager: true }
    )

    const forbiddenTokens = [
      'topological_sort',
      'forward_pass',
      'backward_pass',
      'kahn',
      'cpi',
      'spi',
      'cost_variance',
      'forecast',
      'prediction',
      'gemini',
    ]

    for (const [filePath, content] of Object.entries(rawFiles)) {
      const lower = content.toLowerCase()
      for (const token of forbiddenTokens) {
        expect(
          lower.includes(token),
          `Found forbidden calculation/ML token "${token}" in file: ${filePath}`
        ).toBe(false)
      }
    }
  })
})
