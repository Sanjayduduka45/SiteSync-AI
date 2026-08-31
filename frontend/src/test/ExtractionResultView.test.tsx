/**
 * Tests for ExtractionResultView component with Phase 6.7 Matching integration.
 */

import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'
import { ExtractionResultView } from '@/features/extractions/components/ExtractionResultView'
import { ProjectContext } from '@/features/projects/ProjectContext'
import type { ExtractionRecord } from '@/features/extractions/types'

const mockProjectValue = {
  projects: [
    {
      projectId: 'proj-1',
      projectName: 'Test Project',
      projectCode: 'TEST-2026',
      role: 'planner' as const,
    },
  ],
  selectedProject: {
    projectId: 'proj-1',
    projectName: 'Test Project',
    projectCode: 'TEST-2026',
    role: 'planner' as const,
  },
  selectedProjectId: 'proj-1',
  selectProject: vi.fn(),
  currentRole: 'planner' as const,
  loadingProjects: false,
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectContext.Provider value={mockProjectValue}>
        {ui}
      </ProjectContext.Provider>
    </QueryClientProvider>
  )
}

describe('ExtractionResultView', () => {
  const baseExtraction: ExtractionRecord = {
    id: 'ext-test-1',
    project_id: 'proj-1',
    field_input_id: 'inp-1',
    status: 'completed',
    extracted_data: {
      raw_input_id: 'inp-1',
      extracted_activities: [
        {
          description: 'Erected 10 spools on Rack 3',
          progress_value: 10,
          progress_unit: 'spools',
          discipline: 'Piping',
          location: 'Rack 3 Area',
          event_date: '2026-08-30',
          constraints: ['Crane unavailable until 10am', 'Rain delay for 1 hour'],
          evidence_tokens: ['erected 10 spools', 'Rack 3'],
        },
      ],
      extraction_confidence: 0.95,
      model_version: 'gemini-1.5-flash:extraction_v1',
    },
    confidence_score: 0.95,
    model_version: 'gemini-1.5-flash:extraction_v1',
    error_message: null,
    created_at: '2026-08-30T12:00:00Z',
    updated_at: '2026-08-30T12:00:00Z',
  }

  it('renders high confidence correctly (>= 0.85)', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.getByText(/High · 95%/i)).toBeInTheDocument()
  })

  it('renders medium confidence correctly (0.60 - 0.84)', () => {
    const medExtraction: ExtractionRecord = {
      ...baseExtraction,
      confidence_score: 0.72,
    }
    renderWithProviders(<ExtractionResultView extraction={medExtraction} />)
    expect(screen.getByText(/Medium · 72%/i)).toBeInTheDocument()
  })

  it('renders low confidence correctly (< 0.60)', () => {
    const lowExtraction: ExtractionRecord = {
      ...baseExtraction,
      confidence_score: 0.45,
    }
    renderWithProviders(<ExtractionResultView extraction={lowExtraction} />)
    expect(screen.getByText(/Low · 45%/i)).toBeInTheDocument()
  })

  it('renders extracted activity description, discipline, location and date', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.getByText('Erected 10 spools on Rack 3')).toBeInTheDocument()
    expect(screen.getByText('Piping')).toBeInTheDocument()
    expect(screen.getByText('Rack 3 Area')).toBeInTheDocument()
    expect(screen.getByText('2026-08-30')).toBeInTheDocument()
  })

  it('renders progress quantity and unit correctly', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.getByText('10 spools')).toBeInTheDocument()
  })

  it('renders percentage progress correctly', () => {
    const pctExtraction: ExtractionRecord = {
      ...baseExtraction,
      extracted_data: {
        raw_input_id: 'inp-1',
        extracted_activities: [
          {
            description: 'Foundation rebar inspection',
            progress_value: 100,
            progress_unit: '%',
            discipline: 'Civil',
            location: 'Grid 4',
            event_date: '2026-08-30',
            constraints: [],
            evidence_tokens: ['100% complete'],
          },
        ],
        extraction_confidence: 0.90,
        model_version: 'gemini-1.5-flash:extraction_v1',
      },
    }
    renderWithProviders(<ExtractionResultView extraction={pctExtraction} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('handles missing progress gracefully without rendering NaN or null', () => {
    const noProgressExtraction: ExtractionRecord = {
      ...baseExtraction,
      extracted_data: {
        raw_input_id: 'inp-1',
        extracted_activities: [
          {
            description: 'Conducted safety briefing',
            progress_value: null,
            progress_unit: null,
            discipline: 'General',
            location: null,
            event_date: null,
            constraints: [],
            evidence_tokens: [],
          },
        ],
        extraction_confidence: 0.88,
        model_version: 'gemini-1.5-flash:extraction_v1',
      },
    }
    renderWithProviders(<ExtractionResultView extraction={noProgressExtraction} />)
    expect(screen.getByText('Progress not specified')).toBeInTheDocument()
    expect(screen.queryByText(/null/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/NaN/i)).not.toBeInTheDocument()
  })

  it('renders constraints and blockers callouts', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.getByText('Crane unavailable until 10am')).toBeInTheDocument()
    expect(screen.getByText('Rain delay for 1 hour')).toBeInTheDocument()
  })

  it('renders evidence tokens as quoted fragments', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.getByText('"erected 10 spools"')).toBeInTheDocument()
    expect(screen.getByText('"Rack 3"')).toBeInTheDocument()
  })

  it('handles empty evidence list with fallback message', () => {
    const noEvidenceExtraction: ExtractionRecord = {
      ...baseExtraction,
      extracted_data: {
        raw_input_id: 'inp-1',
        extracted_activities: [
          {
            description: 'Site cleanup',
            progress_value: 100,
            progress_unit: '%',
            discipline: 'General',
            constraints: [],
            evidence_tokens: [],
          },
        ],
        extraction_confidence: 0.75,
        model_version: 'gemini-1.5-flash:extraction_v1',
      },
    }
    renderWithProviders(<ExtractionResultView extraction={noEvidenceExtraction} />)
    expect(screen.getByText('No evidence tokens provided.')).toBeInTheDocument()
  })

  it('does not render any prohibited Phase 7+ concepts', () => {
    renderWithProviders(<ExtractionResultView extraction={baseExtraction} />)
    expect(screen.queryByText(/planner approval/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/approved actual/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/variance/i)).not.toBeInTheDocument()
  })
})
