/**
 * Frontend tests for SchedulePage & AI Schedule Matching UI — SiteSync AI Phase 6.7.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SchedulePage from '@/pages/SchedulePage'
import { MatchRecommendationsView } from '@/features/schedules/components/MatchRecommendationsView'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as schedulesApi from '@/features/schedules/api'
import type { MatchRecommendation, ScheduleActivity } from '@/features/schedules/types'

const mockProjectValue = {
  projects: [
    {
      projectId: 'proj-mtp-001',
      projectName: 'MTP – Refinery Expansion',
      projectCode: 'MTP-2026',
      role: 'planner' as const,
    },
  ],
  selectedProject: {
    projectId: 'proj-mtp-001',
    projectName: 'MTP – Refinery Expansion',
    projectCode: 'MTP-2026',
    role: 'planner' as const,
  },
  selectedProjectId: 'proj-mtp-001',
  selectProject: vi.fn(),
  currentRole: 'planner' as const,
  loadingProjects: false,
}

const mockActivities: ScheduleActivity[] = [
  {
    id: 'act-01',
    project_id: 'proj-mtp-001',
    activity_code: 'ACT-1001',
    name: 'Erect Structural Steel Tier 1',
    wbs_code: '1.2.1',
    discipline: 'Civil',
    location: 'Grid 4',
    planned_start_date: '2026-09-01',
    planned_finish_date: '2026-09-15',
    planned_quantity: 250,
    planned_unit: 'tons',
    metadata: {},
    created_at: '2026-08-30T10:00:00Z',
    updated_at: '2026-08-30T10:00:00Z',
  },
  {
    id: 'act-02',
    project_id: 'proj-mtp-001',
    activity_code: 'ACT-2002',
    name: 'Install Underground Sewer Pipe',
    wbs_code: '2.1.3',
    discipline: 'Piping',
    location: 'Zone B',
    planned_start_date: '2026-09-05',
    planned_finish_date: '2026-09-20',
    planned_quantity: 500,
    planned_unit: 'LF',
    metadata: {},
    created_at: '2026-08-30T10:00:00Z',
    updated_at: '2026-08-30T10:00:00Z',
  },
]

function renderWithProviders(ui: React.ReactElement, projectOverride = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={{ ...mockProjectValue, ...projectOverride }}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ProjectContext.Provider>
    </QueryClientProvider>
  )
}

describe('SchedulePage & Schedule Management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders schedule activities correctly', async () => {
    vi.spyOn(schedulesApi, 'getScheduleActivities').mockResolvedValueOnce({
      items: mockActivities,
      total: 2,
      limit: 50,
      offset: 0,
    })

    renderWithProviders(<SchedulePage />)

    expect(screen.getByText(/Project Baseline Schedule/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('ACT-1001')).toBeInTheDocument()
      expect(screen.getByText('Erect Structural Steel Tier 1')).toBeInTheDocument()
      expect(screen.getByText('ACT-2002')).toBeInTheDocument()
      expect(screen.getByText('Install Underground Sewer Pipe')).toBeInTheDocument()
    })
  })

  it('renders empty state when no activities exist', async () => {
    vi.spyOn(schedulesApi, 'getScheduleActivities').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    renderWithProviders(<SchedulePage />)

    await waitFor(() => {
      expect(screen.getByText(/No schedule activities yet/i)).toBeInTheDocument()
      expect(
        screen.getByText(/Create the project's baseline schedule to enable AI matching/i)
      ).toBeInTheDocument()
    })
  })

  it('planner and admin can see + Add Schedule Activity button', async () => {
    vi.spyOn(schedulesApi, 'getScheduleActivities').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    renderWithProviders(<SchedulePage />, { currentRole: 'planner' })
    expect(screen.getByText('+ Add Schedule Activity')).toBeInTheDocument()
  })

  it('viewer cannot see + Add Schedule Activity button', async () => {
    vi.spyOn(schedulesApi, 'getScheduleActivities').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })

    renderWithProviders(<SchedulePage />, { currentRole: 'viewer' })
    expect(screen.queryByText('+ Add Schedule Activity')).not.toBeInTheDocument()
  })

  it('validates activity creation form inputs', async () => {
    vi.spyOn(schedulesApi, 'getScheduleActivities').mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    })
    const createSpy = vi.spyOn(schedulesApi, 'createScheduleActivity').mockResolvedValueOnce(mockActivities[0])

    renderWithProviders(<SchedulePage />, { currentRole: 'planner' })

    // Open modal
    fireEvent.click(screen.getByText('+ Add Schedule Activity'))
    expect(screen.getByText('Add Baseline Schedule Activity')).toBeInTheDocument()

    // Fill form
    fireEvent.change(screen.getByLabelText(/Activity Code/i), { target: { value: 'ACT-NEW' } })
    fireEvent.change(screen.getByLabelText(/Activity Name/i), { target: { value: 'New Test Activity' } })

    fireEvent.click(screen.getByText('Save Activity'))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('proj-mtp-001', expect.objectContaining({
        activity_code: 'ACT-NEW',
        name: 'New Test Activity',
      }))
    })
  })
})

describe('MatchRecommendationsView & AI Matching UI', () => {
  const mockMatches: MatchRecommendation[] = [
    {
      id: 'match-1',
      project_id: 'proj-mtp-001',
      extraction_id: 'ext-1',
      activity_index: 0,
      recommended_activity_id: 'act-01',
      recommended_activity_code: 'ACT-1001',
      recommended_activity_name: 'Erect Structural Steel Tier 1',
      confidence_score: 0.94,
      scoring_breakdown: {
        semantic_similarity: 0.95,
        discipline_contribution: 0.15,
        location_contribution: 0.10,
        temporal_contribution: 0.05,
      },
      alternative_matches: [
        {
          schedule_activity_id: 'act-02',
          activity_code: 'ACT-2002',
          activity_name: 'Install Underground Sewer Pipe',
          confidence_score: 0.65,
          discipline: 'Piping',
          location: 'Zone B',
          planned_start_date: '2026-09-05',
          planned_finish_date: '2026-09-20',
          scoring_breakdown: {
            semantic_similarity: 0.60,
            discipline_contribution: 0.0,
            location_contribution: 0.05,
            temporal_contribution: 0.0,
          },
        },
      ],
      created_at: '2026-08-30T12:00:00Z',
      updated_at: '2026-08-30T12:00:00Z',
    },
  ]

  it('renders match recommendation with high confidence and breakdown', () => {
    render(
      <MatchRecommendationsView
        matches={mockMatches}
        isLoading={false}
        isMatching={false}
        canMatch={true}
        onTriggerMatch={vi.fn()}
      />
    )

    expect(screen.getByText('Schedule Alignment')).toBeInTheDocument()
    expect(screen.getByText(/Recommended Match \(Activity #1\)/i)).toBeInTheDocument()
    expect(screen.getByText('ACT-1001')).toBeInTheDocument()
    expect(screen.getByText('Erect Structural Steel Tier 1')).toBeInTheDocument()
    expect(screen.getByText(/HIGH · 94%/i)).toBeInTheDocument()

    // Alternatives
    expect(screen.getByText(/Alternative Candidates \(1\)/i)).toBeInTheDocument()
    expect(screen.getByText('ACT-2002')).toBeInTheDocument()
    expect(screen.getByText('65%')).toBeInTheDocument()
  })

  it('toggles explainable scoring breakdown', () => {
    render(
      <MatchRecommendationsView
        matches={mockMatches}
        isLoading={false}
        isMatching={false}
        canMatch={true}
        onTriggerMatch={vi.fn()}
      />
    )

    const toggleBtn = screen.getByText('View Scoring Breakdown ▼')
    fireEvent.click(toggleBtn)

    expect(screen.getByText('Semantic Similarity (70%)')).toBeInTheDocument()
    expect(screen.getByText('95%')).toBeInTheDocument()
    expect(screen.getByText('Discipline Alignment (15%)')).toBeInTheDocument()
    expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(1)
  })

  it('renders empty matches state with trigger button for planner', () => {
    const triggerSpy = vi.fn()
    render(
      <MatchRecommendationsView
        matches={[]}
        isLoading={false}
        isMatching={false}
        canMatch={true}
        onTriggerMatch={triggerSpy}
      />
    )

    expect(
      screen.getByText(/No schedule matches yet. Run Match to Schedule to generate recommendations./i)
    ).toBeInTheDocument()

    fireEvent.click(screen.getByText('Match to Schedule'))
    expect(triggerSpy).toHaveBeenCalledTimes(1)
  })

  it('renders matching in-progress loading state', () => {
    render(
      <MatchRecommendationsView
        matches={[]}
        isLoading={false}
        isMatching={true}
        canMatch={true}
        onTriggerMatch={vi.fn()}
      />
    )

    expect(screen.getByText('Matching to schedule activities…')).toBeInTheDocument()
    expect(
      screen.getByText(/Generating embeddings, performing vector search, and calculating contextual scores./i)
    ).toBeInTheDocument()
  })

  it('does not contain prohibited Phase 7/8/9 concepts', () => {
    render(
      <MatchRecommendationsView
        matches={mockMatches}
        isLoading={false}
        isMatching={false}
        canMatch={true}
        onTriggerMatch={vi.fn()}
      />
    )

    expect(screen.queryByText(/planner approval/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/approved actual/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/variance/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/critical path/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/risk heatmap/i)).not.toBeInTheDocument()
  })
})
