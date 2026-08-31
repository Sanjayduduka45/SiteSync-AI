/**
 * Tests for ApprovedActualsPage component.
 * Verifies read-only behavior for all roles (Viewer, Supervisor, Planner, Admin),
 * server pagination, date and activity filtering, validation, and error states.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ApprovedActualsPage from '@/pages/ApprovedActualsPage'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as decisionsApi from '@/features/decisions/api'
import * as schedulesApi from '@/features/schedules/api'
import type { ApprovedActualListResponse } from '@/features/decisions/types'

vi.mock('@/features/decisions/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/decisions/api')>()
  return {
    ...actual,
    getApprovedActuals: vi.fn(),
  }
})

vi.mock('@/features/schedules/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/schedules/api')>()
  return {
    ...actual,
    getScheduleActivities: vi.fn(),
  }
})

const mockScheduleData = {
  items: [
    {
      id: 'act-1',
      project_id: 'proj-1',
      activity_code: 'ACT-101',
      name: 'Steel Framing',
      discipline: 'Civil',
      created_at: '2026-08-30T12:00:00Z',
      updated_at: '2026-08-30T12:00:00Z',
    },
  ],
  total: 1,
  limit: 100,
  offset: 0,
}

const mockActualsData: ApprovedActualListResponse = {
  items: [
    {
      id: 'actual-1',
      project_id: 'proj-1',
      schedule_activity_id: 'act-1',
      extraction_id: 'ext-1',
      match_id: 'match-1',
      activity_index: 0,
      actual_quantity: 10,
      actual_unit: 'tons',
      actual_date: '2026-08-30',
      source_evidence: ['erected 10 tons'],
      approved_by: 'planner-john',
      approved_at: '2026-08-30T14:00:00Z',
      notes: 'Verified on site',
      is_modified: false,
      created_at: '2026-08-30T14:00:00Z',
      updated_at: '2026-08-30T14:00:00Z',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

function renderPage(
  role = 'planner',
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
) {
  const mockProjectContext = {
    projects: [
      {
        projectId: 'proj-1',
        projectName: 'Commercial Tower A',
        projectCode: 'TWR-A',
        role: role as any,
      },
    ],
    selectedProject: {
      projectId: 'proj-1',
      projectName: 'Commercial Tower A',
      projectCode: 'TWR-A',
      role: role as any,
    },
    selectedProjectId: 'proj-1',
    selectProject: vi.fn(),
    currentRole: role as any,
    loadingProjects: false,
  }

  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={mockProjectContext}>
        <ApprovedActualsPage />
      </ProjectContext.Provider>
    </QueryClientProvider>
  )
}

describe('ApprovedActualsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(schedulesApi.getScheduleActivities).mockResolvedValue(mockScheduleData)
    vi.mocked(decisionsApi.getApprovedActuals).mockResolvedValue(mockActualsData)
  })

  it('renders page title, subtitle, and badge', async () => {
    renderPage('planner')
    expect(screen.getByText('Approved Actuals')).toBeInTheDocument()
    expect(
      screen.getByText(/Human-verified field progress approved through SiteSync AI's planner review workflow\./i)
    ).toBeInTheDocument()
    expect(screen.getByText('Official verified progress records')).toBeInTheDocument()
  })

  it('allows Viewer role to view records (read-only)', async () => {
    renderPage('viewer')
    await waitFor(() => {
      expect(screen.getByText('ACT-101')).toBeInTheDocument()
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('tons')).toBeInTheDocument()
    })
    // No mutation controls exist
    expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Reject/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Modify/i })).not.toBeInTheDocument()
  })

  it('allows Supervisor role to view records', async () => {
    renderPage('supervisor')
    await waitFor(() => {
      expect(screen.getByText('ACT-101')).toBeInTheDocument()
    })
  })

  it('allows Planner role to view records', async () => {
    renderPage('planner')
    await waitFor(() => {
      expect(screen.getByText('ACT-101')).toBeInTheDocument()
    })
  })

  it('allows Admin role to view records', async () => {
    renderPage('admin')
    await waitFor(() => {
      expect(screen.getByText('ACT-101')).toBeInTheDocument()
    })
  })

  it('renders empty state when total is 0', async () => {
    vi.mocked(decisionsApi.getApprovedActuals).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    renderPage('planner')
    await waitFor(() => {
      expect(screen.getByText('No approved actuals yet.')).toBeInTheDocument()
    })
  })

  it('renders safe error message for 403 Forbidden', async () => {
    vi.mocked(decisionsApi.getApprovedActuals).mockRejectedValue(
      new Error('403 Forbidden: Project access denied')
    )

    renderPage('viewer')
    await waitFor(() => {
      expect(
        screen.getByText("You don't have permission to view approved actuals.")
      ).toBeInTheDocument()
    })
  })

  it('renders safe error message for 500 Internal Error', async () => {
    vi.mocked(decisionsApi.getApprovedActuals).mockRejectedValue(
      new Error('500 Internal Server Error: Database failure with SUPABASE_KEY')
    )

    renderPage('planner')
    await waitFor(() => {
      expect(
        screen.getByText('Unable to load approved actuals. Please try again.')
      ).toBeInTheDocument()
      expect(screen.queryByText(/SUPABASE_KEY/i)).not.toBeInTheDocument()
    })
  })

  it('validates date range and blocks invalid search request', async () => {
    renderPage('planner')

    const fromInput = screen.getByLabelText(/Date From/i)
    const toInput = screen.getByLabelText(/Date To/i)

    await userEvent.type(fromInput, '2026-08-30')
    await userEvent.type(toInput, '2026-08-01')

    expect(
      screen.getByText('From date must be on or before To date.')
    ).toBeInTheDocument()

    // getApprovedActuals should NOT have been called with the invalid date range
    expect(decisionsApi.getApprovedActuals).not.toHaveBeenCalledWith(
      'proj-1',
      50,
      0,
      undefined,
      '2026-08-30',
      '2026-08-01'
    )
  })

  it('filters by schedule activity and clears filters', async () => {
    renderPage('planner')

    // Wait for schedule activities to load into select
    await waitFor(() => {
      expect(screen.getByText(/ACT-101 — Steel Framing/i)).toBeInTheDocument()
    })

    const select = screen.getByLabelText(/Filter by Schedule Activity/i)
    await userEvent.selectOptions(select, 'act-1')

    await waitFor(() => {
      expect(decisionsApi.getApprovedActuals).toHaveBeenCalledWith(
        'proj-1',
        50,
        0,
        'act-1',
        undefined,
        undefined
      )
    })


    const clearBtn = screen.getByRole('button', { name: /Clear Filters/i })
    await userEvent.click(clearBtn)

    await waitFor(() => {
      expect(decisionsApi.getApprovedActuals).toHaveBeenCalledWith(
        'proj-1',
        50,
        0,
        undefined,
        undefined,
        undefined
      )
    })
  })

  it('handles server-side pagination next and previous controls', async () => {
    vi.mocked(decisionsApi.getApprovedActuals).mockResolvedValue({
      items: mockActualsData.items,
      total: 100,
      limit: 50,
      offset: 0,
    })

    renderPage('planner')

    await waitFor(() => {
      expect(screen.getByText('Showing 1–50 of 100')).toBeInTheDocument()
    })

    const prevBtn = screen.getByRole('button', { name: /Previous/i })
    const nextBtn = screen.getByRole('button', { name: /Next/i })

    expect(prevBtn).toBeDisabled()
    expect(nextBtn).not.toBeDisabled()

    await userEvent.click(nextBtn)

    await waitFor(() => {
      expect(decisionsApi.getApprovedActuals).toHaveBeenCalledWith(
        'proj-1',
        50,
        50,
        undefined,
        undefined,
        undefined
      )
    })
  })
})
