/**
 * Tests for MatchDecisionControls component.
 * Verifies RBAC visibility, approval confirmation, reject/modify modal triggers,
 * cache invalidation, already-decided states, and error handling.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MatchDecisionControls } from '@/features/decisions/components/MatchDecisionControls'
import * as decisionsApi from '@/features/decisions/api'
import type { ExtractedActivity } from '@/features/extractions/types'
import type { MatchRecommendation } from '@/features/schedules/types'

vi.mock('@/features/decisions/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/decisions/api')>()
  return {
    ...actual,
    approveMatch: vi.fn(),
    rejectMatch: vi.fn(),
    modifyMatch: vi.fn(),
    getMatchDecision: vi.fn(),
  }
})


const mockMatch: MatchRecommendation = {
  id: 'match-101',
  project_id: 'proj-1',
  extraction_id: 'ext-1',
  activity_index: 0,
  recommended_activity_id: 'act-1',
  recommended_activity_code: 'ACT-101',
  recommended_activity_name: 'Erect Steel Tier 1',
  confidence_score: 0.92,
  scoring_breakdown: {
    semantic_similarity: 0.9,
    discipline_contribution: 0.15,
    location_contribution: 0.1,
    temporal_contribution: 0.05,
  },
  alternative_matches: [],
  created_at: '2026-08-30T12:00:00Z',
  updated_at: '2026-08-30T12:00:00Z',
}

const mockActivity: ExtractedActivity = {
  description: 'Erected 12 tons steel in Grid 4',
  progress_value: 12,
  progress_unit: 'tons',
  discipline: 'Civil',
  location: 'Grid 4',
  event_date: '2026-08-30',
  evidence_tokens: ['erected', '12 tons', 'Grid 4'],
}

function renderComponent(
  currentRole = 'planner',
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MatchDecisionControls
        projectId="proj-1"
        extractionId="ext-1"
        match={mockMatch}
        currentRole={currentRole}
        extractedActivity={mockActivity}
      />
    </QueryClientProvider>
  )
}

describe('MatchDecisionControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(decisionsApi.getMatchDecision).mockResolvedValue(null)
  })

  it('renders Approve, Modify, Reject controls for Planner role', async () => {
    renderComponent('planner')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /✓ Approve/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /✎ Modify/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /✕ Reject/i })).toBeInTheDocument()
    })
  })

  it('renders Approve, Modify, Reject controls for Admin role', async () => {
    renderComponent('admin')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /✓ Approve/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /✎ Modify/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /✕ Reject/i })).toBeInTheDocument()
    })
  })

  it('hides mutation controls for Viewer role', async () => {
    renderComponent('viewer')
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/i })).not.toBeInTheDocument()
      expect(
        screen.getByText(/Pending planner review\. Approvals and modifications require Planner or Admin role\./i)
      ).toBeInTheDocument()
    })
  })

  it('hides mutation controls for Supervisor role', async () => {
    renderComponent('supervisor')
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/i })).not.toBeInTheDocument()
      expect(
        screen.getByText(/Pending planner review\. Approvals and modifications require Planner or Admin role\./i)
      ).toBeInTheDocument()
    })
  })

  it('opens confirmation modal and executes approval on confirm', async () => {
    vi.mocked(decisionsApi.approveMatch).mockResolvedValue({
      id: 'actual-1',
      project_id: 'proj-1',
      schedule_activity_id: 'act-1',
      extraction_id: 'ext-1',
      match_id: 'match-101',
      activity_index: 0,
      actual_quantity: 12,
      actual_unit: 'tons',
      actual_date: '2026-08-30',
      source_evidence: [],
      approved_by: 'planner-1',
      approved_at: '2026-08-30T14:00:00Z',
      notes: 'Verified on site',
      is_modified: false,
      created_at: '2026-08-30T14:00:00Z',
      updated_at: '2026-08-30T14:00:00Z',
    })

    renderComponent('planner')
    const approveBtn = await screen.findByRole('button', { name: /✓ Approve/i })
    await userEvent.click(approveBtn)

    // Verify confirmation modal content
    expect(screen.getByText(/Confirm Progress Approval/i)).toBeInTheDocument()
    expect(screen.getByText(/ACT-101/i)).toBeInTheDocument()
    expect(screen.getByText(/Erect Steel Tier 1/i)).toBeInTheDocument()
    expect(screen.getByText(/12 tons/i)).toBeInTheDocument()
    expect(screen.getByText(/2026-08-30/i)).toBeInTheDocument()

    // Add notes and confirm
    const notesInput = screen.getByLabelText(/Planner Notes/i)
    await userEvent.type(notesInput, 'Verified on site')

    const confirmBtn = screen.getByRole('button', { name: /Confirm Approval/i })
    await userEvent.click(confirmBtn)

    expect(decisionsApi.approveMatch).toHaveBeenCalledWith('proj-1', 'match-101', {
      notes: 'Verified on site',
    })
  })

  it('renders DecisionStatusBadge when match has an existing decision', async () => {
    vi.mocked(decisionsApi.getMatchDecision).mockResolvedValue({
      id: 'dec-1',
      project_id: 'proj-1',
      match_id: 'match-101',
      extraction_id: 'ext-1',
      decision: 'approved',
      decided_by: 'planner-alice',
      decided_at: '2026-08-30T15:00:00Z',
      rejection_reason: null,
      original_payload: {},
      modified_payload: null,
      created_at: '2026-08-30T15:00:00Z',
    })

    renderComponent('planner')
    await waitFor(() => {
      expect(screen.getByText('Approved')).toBeInTheDocument()
      expect(screen.getByText('planner-alice')).toBeInTheDocument()
      // Active mutation controls should be hidden by default
      expect(screen.queryByRole('button', { name: /✓ Approve/i })).not.toBeInTheDocument()
    })
  })

  it('renders safe error when mutation returns 403 Forbidden', async () => {
    vi.mocked(decisionsApi.approveMatch).mockRejectedValue(
      new Error('403 Forbidden: INSUFFICIENT_PERMISSIONS')
    )

    renderComponent('planner')
    const approveBtn = await screen.findByRole('button', { name: /✓ Approve/i })
    await userEvent.click(approveBtn)

    const confirmBtn = screen.getByRole('button', { name: /Confirm Approval/i })
    await userEvent.click(confirmBtn)

    await waitFor(() => {
      expect(
        screen.getByText("You don't have permission to make planner decisions.")
      ).toBeInTheDocument()
    })
  })

  it('renders safe error when mutation returns 500 Internal Error', async () => {
    vi.mocked(decisionsApi.approveMatch).mockRejectedValue(
      new Error('500 Internal Server Error: Database failure')
    )

    renderComponent('planner')
    const approveBtn = await screen.findByRole('button', { name: /✓ Approve/i })
    await userEvent.click(approveBtn)

    const confirmBtn = screen.getByRole('button', { name: /Confirm Approval/i })
    await userEvent.click(confirmBtn)

    await waitFor(() => {
      expect(screen.getByText('Unable to save this decision. Please try again.')).toBeInTheDocument()
    })
  })

  it('invalidates relevant queries on successful rejection', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    vi.mocked(decisionsApi.rejectMatch).mockResolvedValue({
      id: 'dec-2',
      project_id: 'proj-1',
      match_id: 'match-101',
      extraction_id: 'ext-1',
      decision: 'rejected',
      decided_by: 'planner-1',
      decided_at: '2026-08-30T16:00:00Z',
      rejection_reason: 'Duplicate record',
      original_payload: {},
      modified_payload: null,
      created_at: '2026-08-30T16:00:00Z',
    })

    renderComponent('planner', queryClient)
    const rejectBtn = await screen.findByRole('button', { name: /✕ Reject/i })
    await userEvent.click(rejectBtn)

    const textarea = screen.getByLabelText(/Why are you rejecting this recommendation\?/i)
    await userEvent.type(textarea, 'Duplicate record')

    const confirmReject = screen.getByRole('button', { name: /Reject Recommendation/i })
    await userEvent.click(confirmReject)

    await waitFor(() => {
      expect(decisionsApi.rejectMatch).toHaveBeenCalledWith('proj-1', 'match-101', {
        rejection_reason: 'Duplicate record',
      })
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['match-decision', 'proj-1', 'match-101'],
      })
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ['extraction-matches', 'proj-1', 'ext-1'],
      })
    })
  })

  it('opens modify modal and executes modification on confirm', async () => {
    vi.mocked(decisionsApi.modifyMatch).mockResolvedValue({
      id: 'actual-2',
      project_id: 'proj-1',
      schedule_activity_id: 'act-1',
      extraction_id: 'ext-1',
      match_id: 'match-101',
      activity_index: 0,
      actual_quantity: 20,
      actual_unit: 'tons',
      actual_date: '2026-08-30',
      source_evidence: [],
      approved_by: 'planner-1',
      approved_at: '2026-08-30T14:00:00Z',
      notes: 'Modified before approval',
      is_modified: true,
      created_at: '2026-08-30T14:00:00Z',
      updated_at: '2026-08-30T14:00:00Z',
    })

    renderComponent('planner')
    const modifyBtn = await screen.findByRole('button', { name: /✎ Modify/i })
    await userEvent.click(modifyBtn)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/Modify & Approve Recommendation/i)).toBeInTheDocument()

    const confirmModifyBtn = screen.getByRole('button', { name: /Save & Approve Changes/i })
    await userEvent.click(confirmModifyBtn)

    await waitFor(() => {
      expect(decisionsApi.modifyMatch).toHaveBeenCalled()
    })
  })

  it('never displays raw secrets, tokens, or stack traces on failure', async () => {
    vi.mocked(decisionsApi.approveMatch).mockRejectedValue(
      new Error('Database error with SUPABASE_SERVICE_ROLE_KEY and Traceback in backend')
    )

    renderComponent('planner')
    const approveBtn = await screen.findByRole('button', { name: /✓ Approve/i })
    await userEvent.click(approveBtn)

    const confirmBtn = screen.getByRole('button', { name: /Confirm Approval/i })
    await userEvent.click(confirmBtn)

    await waitFor(() => {
      expect(screen.getByText('An unexpected error occurred. Please try again.')).toBeInTheDocument()
      expect(screen.queryByText(/SUPABASE_SERVICE_ROLE_KEY/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument()
    })
  })
})

