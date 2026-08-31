import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AuditPage from '@/pages/AuditPage'
import * as auditApi from '@/features/audit/api'
import * as projectContext from '@/features/projects/useProject'

vi.mock('@/features/audit/api')
vi.mock('@/features/projects/useProject')

describe('AuditPage', () => {
  let queryClient: QueryClient

  const mockAuditResponse = {
    items: [
      {
        id: 'event-1',
        project_id: '00000000-0000-0000-0000-000000000001',
        event_type: 'APPROVED_ACTUAL_COMMITTED' as const,
        action: 'COMMIT_ACTUAL' as const,
        entity_type: 'approved_actual',
        entity_id: 'actual-001',
        timestamp: '2026-08-31T15:00:00Z',
        actor: {
          actor_id: 'planner-uuid',
          actor_name: 'Lead Planner',
          actor_email: 'planner@sitesync.ai',
          role: 'planner',
          is_system: false,
        },
        provenance_refs: [],
        payload_summary: { actual_quantity: 120.0 },
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()

    vi.spyOn(projectContext, 'useProject').mockReturnValue({
      projects: [
        {
          projectId: '00000000-0000-0000-0000-000000000001',
          projectName: 'Project Alpha',
          projectCode: 'ALPHA',
          role: 'viewer',
        },
      ],
      selectedProject: {
        projectId: '00000000-0000-0000-0000-000000000001',
        projectName: 'Project Alpha',
        projectCode: 'ALPHA',
        role: 'viewer',
      },
      selectedProjectId: '00000000-0000-0000-0000-000000000001',
      currentRole: 'viewer',
      loadingProjects: false,
      selectProject: vi.fn(),
    })

    vi.mocked(auditApi.getAuditEvents).mockResolvedValue(mockAuditResponse)
    vi.mocked(auditApi.getProvenance).mockResolvedValue({
      project_id: '00000000-0000-0000-0000-000000000001',
      root_entity_type: 'APPROVED_ACTUAL' as const,
      root_entity_id: 'actual-001',
      nodes: [],
      links: [],
      is_complete: true,
      unresolved_links: [],
    })
    vi.mocked(auditApi.formatAuditError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Error'
    )
  })

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <AuditPage />
      </QueryClientProvider>
    )

  it('renders page title, subtitle, and loads audit events from API', async () => {
    renderComponent()

    expect(screen.getByText('Audit Trail')).toBeInTheDocument()
    expect(screen.getByText('Immutable lifecycle history and provenance')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getAllByText('Approved Actual').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('actual-001').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Lead Planner').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('triggers server-side query and resets offset when filter changes', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getAllByText('actual-001').length).toBeGreaterThanOrEqual(1)
    })

    const select = screen.getByLabelText(/Event Type/i)
    await userEvent.selectOptions(select, 'FIELD_INPUT_SUBMITTED')

    await waitFor(() => {
      expect(auditApi.getAuditEvents).toHaveBeenCalledWith(
        '00000000-0000-0000-0000-000000000001',
        expect.objectContaining({ event_type: 'FIELD_INPUT_SUBMITTED', offset: 0 })
      )
    })
  })

  it('opens provenance drawer when View Provenance is clicked', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getAllByText('actual-001').length).toBeGreaterThanOrEqual(1)
    })

    const viewProvBtn = screen.getAllByRole('button', { name: /View Provenance/i })[0]
    await userEvent.click(viewProvBtn)

    await waitFor(() => {
      expect(screen.getByText('Provenance Lineage')).toBeInTheDocument()
    })
  })

  it('renders sanitized error message when audit query fails', async () => {
    vi.mocked(auditApi.getAuditEvents).mockRejectedValue(new Error('500 internal server error'))
    vi.mocked(auditApi.formatAuditError).mockReturnValue('Unable to load audit history. Please try again.')

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('Unable to load audit history. Please try again.')).toBeInTheDocument()
    })
  })

  it('statically scans Phase 10.4 audit runtime files for zero calculation and zero export UI', () => {
    const rawFiles = import.meta.glob<string>(
      ['../features/audit/**/*.ts', '../features/audit/**/*.tsx', '../pages/AuditPage.tsx'],
      { query: '?raw', import: 'default', eager: true }
    )

    const forbiddenTokens = [
      'forward_pass',
      'backward_pass',
      'topological_sort',
      'calculate_variance',
      'calculate_cpm',
      'calculate_risk',
      'export_csv',
      'export_json',
      'download_csv',
      'download_json',
    ]

    for (const [filePath, content] of Object.entries(rawFiles)) {
      const lower = content.toLowerCase()
      for (const token of forbiddenTokens) {
        expect(
          lower.includes(token),
          `Found forbidden calculation/export token "${token}" in file: ${filePath}`
        ).toBe(false)
      }
    }
  })
})
