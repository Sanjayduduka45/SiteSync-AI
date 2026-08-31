/**
 * RejectMatchModal — Modal dialog for recording planner rejection of an AI recommendation.
 * Requires a mandatory human reason/justification.
 */

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'

interface RejectMatchModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (reason: string) => Promise<void>
  isSubmitting: boolean
  recommendedActivityName?: string | null
}

export function RejectMatchModal({
  isOpen,
  onClose,
  onConfirm,
  isSubmitting,
  recommendedActivityName,
}: RejectMatchModalProps) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleClose = useCallback(() => {
    if (isSubmitting) return
    setReason('')
    setError(null)
    onClose()
  }, [isSubmitting, onClose])

  // Support closing on Escape key
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) {
        handleClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isSubmitting, handleClose])


  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmed = reason.trim()
    if (!trimmed) {
      setError('Please provide a reason explaining why this recommendation is being rejected.')
      return
    }

    try {
      await onConfirm(trimmed)
      setReason('')
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reject recommendation')
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-dialog-title"
      aria-describedby="reject-dialog-desc"
    >
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-md w-full overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-rose-50/60">
          <div>
            <h2 id="reject-dialog-title" className="text-sm font-bold text-rose-950">
              Reject AI Recommendation
            </h2>
            <p id="reject-dialog-desc" className="text-xs text-rose-800 mt-0.5">
              Human justification is required for the audit log
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none cursor-pointer disabled:opacity-50"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {recommendedActivityName && (
            <div className="p-3 bg-gray-50 rounded border border-gray-200 text-gray-700">
              <span className="text-[10px] uppercase font-bold text-gray-400 block">
                Target Recommendation
              </span>
              <span className="font-semibold text-gray-900">{recommendedActivityName}</span>
            </div>
          )}

          {error && (
            <div
              className="bg-red-50 border border-red-200 p-3 rounded text-red-700 font-medium"
              role="alert"
            >
              {error}
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="rejection-reason" className="font-bold text-gray-800 block">
              Why are you rejecting this recommendation? <span className="text-red-500">*</span>
            </label>
            <textarea
              id="rejection-reason"
              rows={4}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value)
                if (error) setError(null)
              }}
              disabled={isSubmitting}
              placeholder="e.g. Scope was already executed under Tier 1 contract; not applicable to current WBS."
              className="w-full border border-gray-300 rounded-lg p-2.5 text-xs text-gray-900 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none resize-none disabled:bg-gray-100"
            />
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClose}
              disabled={isSubmitting}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting || !reason.trim()}
              className="bg-rose-700 hover:bg-rose-800 text-white font-semibold text-xs"
            >
              {isSubmitting ? 'Rejecting…' : 'Reject Recommendation'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
