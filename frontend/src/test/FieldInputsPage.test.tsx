/**
 * Frontend tests for FieldInputsPage.
 * Validates input feed rendering, text submission, type filtering, detail drawer, and role restrictions.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FieldInputsPage from '@/pages/FieldInputsPage'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as inputsApi from '@/features/inputs/api'
import type { FieldInput } from '@/features/inputs/types'

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

const mockInputs: FieldInput[] = [
  {
    id: 'inp-01',
    project_id: 'proj-mtp-001',
    submitted_by: 'user-01',
    submitted_by_email: 'supervisor@sitesync.ai',
    input_type: 'text',
    title: 'Daily Morning Shift Notes',
    raw_text: 'Completed 4 spools in Rack 3. Waiting on torque verification.',
    media_path: null,
    media_filename: null,
    media_mime_type: null,
    media_size_bytes: 0,
    media_url: null,
    audio_duration_seconds: null,
    transcription_status: 'none',
    transcription_error: null,
    field_date: '2026-08-30',
    metadata: {},
    created_at: '2026-08-30T10:00:00Z',
    updated_at: '2026-08-30T10:00:00Z',
  },
  {
    id: 'inp-02',
    project_id: 'proj-mtp-001',
    submitted_by: 'user-02',
    submitted_by_email: 'foreman@sitesync.ai',
    input_type: 'voice',
    title: 'Compressor Loop Audio Debrief',
    raw_text: 'Pressure test completed on compressor loop line 14.',
    media_path: 'projects/proj-mtp-001/inputs/inp-02/audio.webm',
    media_filename: 'voice_debrief.webm',
    media_mime_type: 'audio/webm',
    media_size_bytes: 45000,
    media_url: 'https://supabase.local/signed/audio.webm',
    audio_duration_seconds: 14.5,
    transcription_status: 'completed',
    transcription_error: null,
    field_date: '2026-08-30',
    metadata: {},
    created_at: '2026-08-30T11:00:00Z',
    updated_at: '2026-08-30T11:00:00Z',
  },
]

function renderFieldInputsPage(projectOverrides = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={{ ...mockProjectValue, ...projectOverrides }}>
        <MemoryRouter>
          <FieldInputsPage />
        </MemoryRouter>
      </ProjectContext.Provider>
    </QueryClientProvider>
  )
}

describe('FieldInputsPage', () => {
  beforeEach(() => {
    vi.spyOn(inputsApi, 'fetchFieldInputs').mockResolvedValue({
      inputs: mockInputs,
      total: 2,
    })
  })

  it('renders page header and input feed cards', async () => {
    renderFieldInputsPage()

    expect(screen.getByText('Field Inputs')).toBeInTheDocument()
    expect(screen.getByText(/Capture raw construction progress/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Daily Morning Shift Notes')).toBeInTheDocument()
      expect(screen.getByText('Compressor Loop Audio Debrief')).toBeInTheDocument()
    })
  })

  it('submits text note from submission modal', async () => {
    const createSpy = vi.spyOn(inputsApi, 'createTextInput').mockResolvedValue({
      id: 'inp-03',
      project_id: 'proj-mtp-001',
      submitted_by: 'user-01',
      input_type: 'text',
      title: 'Foundation Pour Complete',
      raw_text: 'Poured 30m3 concrete for T-101 equipment pad.',
      media_path: null,
      media_size_bytes: 0,
      transcription_status: 'none',
      field_date: '2026-08-30',
      metadata: {},
      created_at: '2026-08-30T12:00:00Z',
      updated_at: '2026-08-30T12:00:00Z',
    })

    renderFieldInputsPage()

    const submitBtn = screen.getByRole('button', { name: /Submit Field Update/i })
    fireEvent.click(submitBtn)

    expect(screen.getByRole('heading', { name: 'Submit Field Update' })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/Note Title/i), {
      target: { value: 'Foundation Pour Complete' },
    })
    fireEvent.change(screen.getByLabelText(/Field Notes \/ Observations/i), {
      target: { value: 'Poured 30m3 concrete for T-101 equipment pad.' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Submit Field Notes/i }))

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        'proj-mtp-001',
        expect.objectContaining({
          title: 'Foundation Pour Complete',
          raw_text: 'Poured 30m3 concrete for T-101 equipment pad.',
        })
      )
    })
  })

  it('opens detail drawer when clicking an input card', async () => {
    renderFieldInputsPage()

    await waitFor(() => {
      expect(screen.getByText('Daily Morning Shift Notes')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Daily Morning Shift Notes'))

    await waitFor(() => {
      expect(screen.getByText('ID: inp-01')).toBeInTheDocument()
      expect(screen.getByText('Submitted At:')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
    })
  })

  it('disables submission button when user has viewer role', () => {
    renderFieldInputsPage({ currentRole: 'viewer' })
    const submitBtn = screen.getByRole('button', { name: /Submit Field Update/i })
    expect(submitBtn).toBeDisabled()
  })
})
