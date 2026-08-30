/**
 * Frontend tests for EventsPage.
 * Validates event listing, create event modal, progress rendering, detail drawer, and role permissions.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EventsPage from '@/pages/EventsPage'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as eventsApi from '@/features/events/api'
import * as reportsApi from '@/features/reports/api'
import type { FieldEvent } from '@/features/events/types'

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

const mockEvents: FieldEvent[] = [
  {
    id: 'evt-01',
    project_id: 'proj-mtp-001',
    report_id: 'rep-01',
    report_name: 'Daily Progress Report — 18 May',
    event_type: 'Spool Erection',
    description: 'Spool erection completed on Line 24 in Rack 3 Area',
    discipline: 'Piping',
    location: 'Unit-1 / Piping Area',
    event_date: '2025-05-18',
    progress_percent: 100,
    status: 'pending',
    created_at: '2025-05-18T10:00:00Z',
    updated_at: '2025-05-18T10:00:00Z',
  },
]

function renderEventsPage(projectOverrides = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={{ ...mockProjectValue, ...projectOverrides }}>
        <MemoryRouter>
          <EventsPage />
        </MemoryRouter>
      </ProjectContext.Provider>
    </QueryClientProvider>,
  )
}

describe('EventsPage', () => {
  beforeEach(() => {
    vi.spyOn(eventsApi, 'fetchEvents').mockResolvedValue({
      events: mockEvents,
      total: 1,
    })
    vi.spyOn(reportsApi, 'fetchReports').mockResolvedValue({
      reports: [],
      total: 0,
    })
  })

  it('renders page header and field events table', async () => {
    renderEventsPage()

    expect(screen.getByText('Field Events')).toBeInTheDocument()
    expect(screen.getByText(/Structured events captured from construction field information/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Spool Erection')).toBeInTheDocument()
      expect(screen.getByText(/Spool erection completed on Line 24/i)).toBeInTheDocument()
      expect(screen.getByText('100%')).toBeInTheDocument()
    })
  })

  it('opens create event modal and submits new field event', async () => {
    const createSpy = vi.spyOn(eventsApi, 'createEvent').mockResolvedValue({
      id: 'evt-02',
      project_id: 'proj-mtp-001',
      event_type: 'Concrete Pour',
      description: 'Foundation pour for C-101',
      discipline: 'Civil',
      location: 'Area 1',
      event_date: '2025-05-19',
      progress_percent: 100,
      status: 'pending',
      created_at: '2025-05-19T10:00:00Z',
      updated_at: '2025-05-19T10:00:00Z',
    })

    renderEventsPage()

    const createBtn = screen.getByRole('button', { name: /Create Event/i })
    fireEvent.click(createBtn)

    expect(screen.getByText('Create Field Event')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/Spool Erection, Concrete Pour/i), {
      target: { value: 'Concrete Pour' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Spool erection completed on Line 24/i), {
      target: { value: 'Foundation pour for C-101' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Unit-1 \/ Piping Rack 3/i), {
      target: { value: 'Area 1' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Record Event/i }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        'proj-mtp-001',
        expect.objectContaining({
          event_type: 'Concrete Pour',
          description: 'Foundation pour for C-101',
          location: 'Area 1',
        }),
      )
    })
  })

  it('opens event detail drawer with AI pipeline placeholders', async () => {
    renderEventsPage()

    await waitFor(() => {
      expect(screen.getByTestId('event-details-btn-evt-01')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('event-details-btn-evt-01'))

    await waitFor(() => {
      expect(screen.getByText('Schedule Intelligence')).toBeInTheDocument()
      expect(screen.getByText('Not processed')).toBeInTheDocument()
    })
  })

  it('disables create event button when user has viewer role', () => {
    renderEventsPage({ currentRole: 'viewer' })
    const createBtn = screen.getByRole('button', { name: /Create Event/i })
    expect(createBtn).toBeDisabled()
  })
})
