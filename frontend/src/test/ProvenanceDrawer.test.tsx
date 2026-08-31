import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProvenanceDrawer } from '@/features/audit/components/ProvenanceDrawer'
import * as auditApi from '@/features/audit/api'

vi.mock('@/features/audit/api')

describe('ProvenanceDrawer', () => {
  let queryClient: QueryClient

  const mockChain = {
    project_id: '00000000-0000-0000-0000-000000000001',
    root_entity_type: 'APPROVED_ACTUAL' as const,
    root_entity_id: 'act-1',
    nodes: [
      {
        node_id: 'APPROVED_ACTUAL:act-1',
        node_type: 'APPROVED_ACTUAL' as const,
        entity_id: 'act-1',
        title: 'Approved Actual: 50 LF',
        status: 'APPROVED',
        timestamp: '2026-08-31T10:00:00Z',
        details: { actual_quantity: 50 },
      },
    ],
    links: [],
    is_complete: true,
    unresolved_links: [],
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()
    vi.mocked(auditApi.getProvenance).mockResolvedValue(mockChain)
    vi.mocked(auditApi.formatAuditError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Error'
    )
  })

  const renderComponent = (props: {
    entityType: string | null
    entityId: string | null
    onClose?: () => void
  }) =>
    render(
      <QueryClientProvider client={queryClient}>
        <ProvenanceDrawer
          projectId="00000000-0000-0000-0000-000000000001"
          entityType={props.entityType}
          entityId={props.entityId}
          onClose={props.onClose || vi.fn()}
        />
      </QueryClientProvider>
    )

  it('renders nothing when closed (entityType/entityId is null)', () => {
    const { container } = renderComponent({ entityType: null, entityId: null })
    expect(container.firstChild).toBeNull()
  })

  it('renders flyout dialog and calls API when opened', async () => {
    renderComponent({ entityType: 'approved_actual', entityId: 'act-1' })

    expect(screen.getByText('Provenance Lineage')).toBeInTheDocument()

    await waitFor(() => {
      expect(auditApi.getProvenance).toHaveBeenCalledWith(
        '00000000-0000-0000-0000-000000000001',
        'approved_actual',
        'act-1'
      )
      expect(screen.getByText('Approved Actual: 50 LF')).toBeInTheDocument()
    })
  })

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn()
    renderComponent({ entityType: 'approved_actual', entityId: 'act-1', onClose })

    const closeBtn = screen.getByRole('button', { name: /Close provenance panel/i })
    await userEvent.click(closeBtn)

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
