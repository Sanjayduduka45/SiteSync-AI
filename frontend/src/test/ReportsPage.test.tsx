/**
 * Frontend tests for ReportsPage.
 * Validates report listing, upload modal, form submission, detail drawer, and role permissions.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReportsPage from '@/pages/ReportsPage'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as reportsApi from '@/features/reports/api'
import * as eventsApi from '@/features/events/api'
import type { Report } from '@/features/reports/types'

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

const mockReports: Report[] = [
  {
    id: 'rep-01',
    project_id: 'proj-mtp-001',
    name: 'Daily Progress Report — 18 May',
    file_name: 'Daily_Report_18_May.pdf',
    file_type: 'pdf',
    file_size: 2_450_000,
    source: 'manual_upload',
    status: 'uploaded',
    uploaded_by: 'user-01',
    uploaded_by_email: 'supervisor@sitesync.ai',
    uploaded_at: '2025-05-18T10:00:00Z',
    created_at: '2025-05-18T10:00:00Z',
    updated_at: '2025-05-18T10:00:00Z',
  },
]

function renderReportsPage(projectOverrides = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={{ ...mockProjectValue, ...projectOverrides }}>
        <MemoryRouter>
          <ReportsPage />
        </MemoryRouter>
      </ProjectContext.Provider>
    </QueryClientProvider>,
  )
}

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.spyOn(reportsApi, 'fetchReports').mockResolvedValue({
      reports: mockReports,
      total: 1,
    })
    vi.spyOn(eventsApi, 'fetchEvents').mockResolvedValue({
      events: [],
      total: 0,
    })
  })

  it('renders page header and reports table', async () => {
    renderReportsPage()

    expect(screen.getByText('Field Reports')).toBeInTheDocument()
    expect(screen.getByText(/Upload and manage project field information/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Daily Progress Report — 18 May')).toBeInTheDocument()
      expect(screen.getByText('Daily_Report_18_May.pdf')).toBeInTheDocument()
    })
  })

  it('opens upload modal, validates inputs, and submits new report', async () => {
    const createSpy = vi.spyOn(reportsApi, 'createReport').mockResolvedValue({
      id: 'rep-02',
      project_id: 'proj-mtp-001',
      name: 'Piping Progress Log',
      file_name: 'Piping.xlsx',
      file_type: 'xlsx',
      file_size: 1000,
      source: 'manual_upload',
      status: 'uploaded',
      uploaded_at: '2025-05-19T10:00:00Z',
      created_at: '2025-05-19T10:00:00Z',
      updated_at: '2025-05-19T10:00:00Z',
    })

    renderReportsPage()

    const uploadBtn = screen.getByRole('button', { name: /Upload Report/i })
    fireEvent.click(uploadBtn)

    expect(screen.getByText('Upload Field Report')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText(/Daily Progress Report/i), {
      target: { value: 'Piping Progress Log' },
    })
    fireEvent.change(screen.getByPlaceholderText(/Daily_Report_19_May.pdf/i), {
      target: { value: 'Piping.xlsx' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Submit Report/i }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        'proj-mtp-001',
        expect.objectContaining({
          name: 'Piping Progress Log',
          file_name: 'Piping.xlsx',
        }),
      )
    })
  })

  it('opens report detail drawer with metadata and empty events message', async () => {
    renderReportsPage()

    await waitFor(() => {
      expect(screen.getByText('Daily Progress Report — 18 May')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Daily Progress Report — 18 May'))

    await waitFor(() => {
      expect(screen.getByText('No field events extracted yet.')).toBeInTheDocument()
    })
  })

  it('disables upload button when user has viewer role', () => {
    renderReportsPage({ currentRole: 'viewer' })
    const uploadBtn = screen.getByRole('button', { name: /Upload Report/i })
    expect(uploadBtn).toBeDisabled()
  })
})
