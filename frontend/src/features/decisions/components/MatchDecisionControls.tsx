/**
 * MatchDecisionControls — Renders decision actions (Approve, Reject, Modify) or
 * latest DecisionStatusBadge for an AI match recommendation.
 * Enforces "AI recommends. Humans decide."
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import type { ExtractedActivity } from '@/features/extractions/types'
import type { MatchRecommendation } from '@/features/schedules/types'
import {
  approveMatch,
  rejectMatch,
  modifyMatch,
  getMatchDecision,
  formatDecisionError,
} from '../api'
import type { ModifyMatchRequest } from '../types'
import { DecisionStatusBadge } from './DecisionStatusBadge'
import { ModifyMatchModal } from './ModifyMatchModal'
import { RejectMatchModal } from './RejectMatchModal'

interface MatchDecisionControlsProps {
  projectId: string
  extractionId: string
  match: MatchRecommendation
  currentRole?: string
  extractedActivity?: ExtractedActivity
}

export function MatchDecisionControls({
  projectId,
  extractionId,
  match,
  currentRole,
  extractedActivity,
}: MatchDecisionControlsProps) {
  const queryClient = useQueryClient()
  const isAuthorized = currentRole === 'planner' || currentRole === 'admin'

  const [isApproveConfirmOpen, setIsApproveConfirmOpen] = useState(false)
  const [approveNotes, setApproveNotes] = useState('')
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false)
  const [isModifyModalOpen, setIsModifyModalOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Query latest decision state for this match
  const {
    data: decision,
    isLoading: isLoadingDecision,
  } = useQuery({
    queryKey: ['match-decision', projectId, match.id],
    queryFn: () => getMatchDecision(projectId, match.id),
    enabled: !!projectId && !!match.id,
  })

  const invalidateRelevantQueries = () => {
    queryClient.invalidateQueries({
      queryKey: ['match-decision', projectId, match.id],
    })
    queryClient.invalidateQueries({
      queryKey: ['extraction-matches', projectId, extractionId],
    })
  }

  // Approve Mutation
  const approveMutation = useMutation({
    mutationFn: async (notes?: string) => {
      return approveMatch(projectId, match.id, { notes })
    },
    onSuccess: () => {
      setActionError(null)
      setIsApproveConfirmOpen(false)
      setApproveNotes('')
      invalidateRelevantQueries()
    },
    onError: (err: unknown) => {
      setActionError(formatDecisionError(err))
    },
  })

  // Reject Mutation
  const rejectMutation = useMutation({
    mutationFn: async (reason: string) => {
      return rejectMatch(projectId, match.id, { rejection_reason: reason })
    },
    onSuccess: () => {
      setActionError(null)
      setIsRejectModalOpen(false)
      invalidateRelevantQueries()
    },
    onError: (err: unknown) => {
      setActionError(formatDecisionError(err))
    },
  })

  // Modify Mutation
  const modifyMutation = useMutation({
    mutationFn: async (payload: ModifyMatchRequest) => {
      return modifyMatch(projectId, match.id, payload)
    },
    onSuccess: () => {
      setActionError(null)
      setIsModifyModalOpen(false)
      invalidateRelevantQueries()
    },
    onError: (err: unknown) => {
      setActionError(formatDecisionError(err))
    },
  })

  const isPending = approveMutation.isPending || rejectMutation.isPending || modifyMutation.isPending

  // Support closing approve dialog on Escape key
  useEffect(() => {
    if (!isApproveConfirmOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isPending) {
        setIsApproveConfirmOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isApproveConfirmOpen, isPending])

  if (isLoadingDecision) {
    return (
      <div className="pt-2 text-gray-400 text-[11px] flex items-center gap-1.5">
        <span className="inline-block h-3 w-3 animate-spin rounded-full border border-gray-400 border-t-transparent" />
        Checking decision status…
      </div>
    )
  }

  // If a decision already exists, render DecisionStatusBadge
  if (decision) {
    return (
      <div className="pt-2">
        <DecisionStatusBadge decision={decision} />
      </div>
    )
  }

  // If user does not have mutation permissions (Viewer / Supervisor)
  if (!isAuthorized) {
    return (
      <div className="pt-2 text-[11px] text-gray-400 italic">
        Pending planner review. Approvals and modifications require Planner or Admin role.
      </div>
    )
  }

  const activityCode = match.recommended_activity_code || 'ACT'
  const activityName = match.recommended_activity_name || 'Recommended Activity'
  const progressVal = extractedActivity?.progress_value ?? '—'
  const progressUnit = extractedActivity?.progress_unit ?? ''
  const eventDate = extractedActivity?.event_date ?? 'Today'

  return (
    <div className="space-y-3 pt-3 border-t border-gray-100" data-testid="match-decision-controls">
      {actionError && (
        <div
          className="bg-red-50 border border-red-200 p-2.5 rounded-lg text-xs text-red-700 font-medium"
          role="alert"
        >
          {actionError}
        </div>
      )}

      {/* Decision Buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          onClick={() => {
            setActionError(null)
            setIsApproveConfirmOpen(true)
          }}
          disabled={isPending}
          className="bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold h-8 px-3"
        >
          ✓ Approve
        </Button>

        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setActionError(null)
            setIsModifyModalOpen(true)
          }}
          disabled={isPending}
          className="text-xs border-gray-300 text-gray-800 hover:bg-gray-50 h-8 px-3 font-medium"
        >
          ✎ Modify
        </Button>

        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setActionError(null)
            setIsRejectModalOpen(true)
          }}
          disabled={isPending}
          className="text-xs border-rose-300 text-rose-700 hover:bg-rose-50 h-8 px-3 font-medium"
        >
          ✕ Reject
        </Button>
      </div>

      {/* Approve Confirmation Dialog */}
      {isApproveConfirmOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="approve-dialog-title"
          aria-describedby="approve-dialog-desc"
        >
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-md w-full overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 bg-emerald-50/60">
              <h2 id="approve-dialog-title" className="text-sm font-bold text-emerald-950">
                Confirm Progress Approval
              </h2>
              <p id="approve-dialog-desc" className="text-xs text-emerald-800 mt-0.5">
                This will create an official approved construction progress record
              </p>
            </div>

            <div className="p-6 space-y-4 text-xs">
              <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200 space-y-2">
                <div>
                  <span className="text-[10px] uppercase font-bold text-gray-400 block">
                    Target Activity
                  </span>
                  <span className="font-bold text-gray-900">
                    <span className="font-mono text-gray-600 mr-1">{activityCode}</span>
                    {activityName}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200/60">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-gray-400 block">
                      Quantity
                    </span>
                    <span className="font-semibold text-gray-800">
                      {progressVal} {progressUnit}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-gray-400 block">
                      Work Date
                    </span>
                    <span className="font-semibold text-gray-800">{eventDate}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="approve-notes" className="font-bold text-gray-800 block">
                  Planner Notes (Optional)
                </label>
                <textarea
                  id="approve-notes"
                  rows={2}
                  value={approveNotes}
                  onChange={(e) => setApproveNotes(e.target.value)}
                  disabled={approveMutation.isPending}
                  placeholder="Add any verification comments for the audit log..."
                  className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-emerald-500 outline-none resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsApproveConfirmOpen(false)}
                  disabled={approveMutation.isPending}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => approveMutation.mutate(approveNotes)}
                  disabled={approveMutation.isPending}
                  className="bg-emerald-700 hover:bg-emerald-800 text-white font-semibold text-xs"
                >
                  {approveMutation.isPending ? 'Approving…' : 'Confirm Approval'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      <RejectMatchModal
        isOpen={isRejectModalOpen}
        onClose={() => setIsRejectModalOpen(false)}
        onConfirm={async (reason) => {
          await rejectMutation.mutateAsync(reason)
        }}
        isSubmitting={rejectMutation.isPending}
        recommendedActivityName={`${activityCode} — ${activityName}`}
      />

      {/* Modify Modal */}
      <ModifyMatchModal
        isOpen={isModifyModalOpen}
        onClose={() => setIsModifyModalOpen(false)}
        onConfirm={async (payload) => {
          await modifyMutation.mutateAsync(payload)
        }}
        isSubmitting={modifyMutation.isPending}
        projectId={projectId}
        initialActivityId={match.recommended_activity_id}
        initialActivityName={`${activityCode} — ${activityName}`}
        initialQuantity={extractedActivity?.progress_value}
        initialUnit={extractedActivity?.progress_unit}
        initialDate={extractedActivity?.event_date}
        initialNotes=""
      />
    </div>
  )
}
