/**
 * Frontend tests for FieldInputsPage.
 * Validates input feed rendering, text submission, type filtering, detail drawer,
 * role restrictions, and Phase 5 AI extraction status / triggers.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FieldInputsPage from '@/pages/FieldInputsPage'
import { ProjectContext } from '@/features/projects/ProjectContext'
import * as inputsApi from '@/features/inputs/api'
import * as extractionsApi from '@/features/extractions/api'
import type { FieldInput } from '@/features/inputs/types'
import type { ExtractionRecord } from '@/features/extractions/types'

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

const mockExtractions: ExtractionRecord[] = [
  {
    id: 'ext-01',
    project_id: 'proj-mtp-001',
    field_input_id: 'inp-01',
    status: 'completed',
    extracted_data: {
      raw_input_id: 'inp-01',
      extracted_activities: [
        {
          description: 'Completed 4 spools in Rack 3',
          progress_value: 4,
          progress_unit: 'spools',
          discipline: 'Piping',
          location: 'Rack 3',
          event_date: '2026-08-30',
          constraints: [],
          evidence_tokens: ['Completed 4 spools in Rack 3'],
        },
      ],
      extraction_confidence: 0.95,
      model_version: 'gemini-1.5-flash:extraction_v1',
    },
    confidence_score: 0.95,
    model_version: 'gemini-1.5-flash:extraction_v1',
    error_message: null,
    created_at: '2026-08-30T10:05:00Z',
    updated_at: '2026-08-30T10:05:00Z',
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
    vi.spyOn(extractionsApi, 'getProjectExtractions').mockResolvedValue({
      extractions: mockExtractions,
      total: 1,
    })
    vi.spyOn(extractionsApi, 'getInputExtractions').mockResolvedValue({
      extractions: mockExtractions,
      total: 1,
    })
  })

  it('renders page header and input feed cards with extraction status', async () => {
    renderFieldInputsPage()

    expect(screen.getByText('Field Inputs')).toBeInTheDocument()
    expect(screen.getByText(/Capture raw construction progress/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Daily Morning Shift Notes')).toBeInTheDocument()
      expect(screen.getByText('Compressor Loop Audio Debrief')).toBeInTheDocument()
      // Card 1 has extraction -> Extracted badge
      expect(screen.getByText(/Extracted \(95%\)/i)).toBeInTheDocument()
      // Card 2 has no extraction -> Unprocessed badge
      expect(screen.getByText('Unprocessed')).toBeInTheDocument()
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

  it('opens detail drawer and displays extraction results', async () => {
    renderFieldInputsPage()

    await waitFor(() => {
      expect(screen.getByText('Daily Morning Shift Notes')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Daily Morning Shift Notes'))

    await waitFor(() => {
      expect(screen.getByText('ID: inp-01')).toBeInTheDocument()
      expect(screen.getByText(/AI Progress Extraction/i)).toBeInTheDocument()
      expect(screen.getByText('High · 95%')).toBeInTheDocument()
      expect(screen.getByText('Completed 4 spools in Rack 3')).toBeInTheDocument()
    })
  })

  it('allows planner to re-run extraction from drawer', async () => {
    const triggerSpy = vi.spyOn(extractionsApi, 'triggerExtraction').mockResolvedValue(mockExtractions[0])

    renderFieldInputsPage({ currentRole: 'planner' })

    await waitFor(() => {
      expect(screen.getByText('Daily Morning Shift Notes')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Daily Morning Shift Notes'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Re-run Extraction/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Re-run Extraction/i }))

    await waitFor(() => {
      expect(triggerSpy).toHaveBeenCalledWith('proj-mtp-001', 'inp-01')
    })
  })

  it('disables submission button when user has viewer role', () => {
    renderFieldInputsPage({ currentRole: 'viewer' })
    const submitBtn = screen.getByRole('button', { name: /Submit Field Update/i })
    expect(submitBtn).toBeDisabled()
  })
})
