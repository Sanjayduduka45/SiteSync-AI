/**
 * ModifyMatchModal — Modal dialog for modifying AI recommendation values
 * (reassigning baseline activity, overriding quantity/date/unit) and executing approval.
 */

import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { getScheduleActivities } from '@/features/schedules/api'
import type { ModifyMatchRequest } from '../types'

interface ModifyMatchModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (payload: ModifyMatchRequest) => Promise<void>
  isSubmitting: boolean
  projectId: string
  initialActivityId: string
  initialActivityName?: string | null
  initialQuantity?: number | null
  initialUnit?: string | null
  initialDate?: string | null
  initialNotes?: string | null
}

export function ModifyMatchModal({
  isOpen,
  onClose,
  onConfirm,
  isSubmitting,
  projectId,
  initialActivityId,
  initialActivityName,
  initialQuantity,
  initialUnit,
  initialDate,
  initialNotes,
}: ModifyMatchModalProps) {
  const [selectedActivityId, setSelectedActivityId] = useState(initialActivityId)
  const [quantity, setQuantity] = useState(
    initialQuantity !== undefined && initialQuantity !== null ? String(initialQuantity) : ''
  )
  const [unit, setUnit] = useState(initialUnit || '')
  const [dateVal, setDateVal] = useState(
    initialDate || new Date().toISOString().split('T')[0]
  )
  const [notes, setNotes] = useState(initialNotes || '')
  const [validationError, setValidationError] = useState<string | null>(null)

  // Fetch baseline activities for this project
  const { data: scheduleData, isLoading: isLoadingActivities } = useQuery({
    queryKey: ['schedule-activities', projectId],
    queryFn: () => getScheduleActivities(projectId, 100, 0),
    enabled: isOpen && !!projectId,
  })

  const handleClose = useCallback(() => {
    if (isSubmitting) return
    setValidationError(null)
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
    setValidationError(null)

    if (!selectedActivityId) {
      setValidationError('Please select a target schedule activity.')
      return
    }

    if (!dateVal) {
      setValidationError('Work date is required.')
      return
    }

    let parsedQty: number | undefined = undefined
    if (quantity.trim() !== '') {
      const num = parseFloat(quantity)
      if (isNaN(num) || num < 0) {
        setValidationError('Quantity must be a non-negative number (>= 0).')
        return
      }
      parsedQty = num
    }

    const payload: ModifyMatchRequest = {
      schedule_activity_id: selectedActivityId,
      actual_quantity: parsedQty,
      actual_unit: unit.trim() || undefined,
      actual_date: dateVal,
      notes: notes.trim() || undefined,
    }

    try {
      await onConfirm(payload)
      setValidationError(null)
    } catch (err: unknown) {
      setValidationError(err instanceof Error ? err.message : 'Failed to save modifications')
    }
  }

  const activities = scheduleData?.items || []

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modify-dialog-title"
      aria-describedby="modify-dialog-desc"
    >
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-lg w-full overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-blue-50/60">
          <div>
            <h2 id="modify-dialog-title" className="text-sm font-bold text-blue-950">
              Modify & Approve Recommendation
            </h2>
            <p id="modify-dialog-desc" className="text-xs text-blue-800 mt-0.5">
              Override schedule activity or actual values before saving
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
        <form onSubmit={handleSubmit} noValidate className="p-6 overflow-y-auto space-y-4 text-xs">
          {validationError && (
            <div
              className="bg-red-50 border border-red-200 p-3 rounded text-red-700 font-medium"
              role="alert"
            >
              {validationError}
            </div>
          )}

          {/* Schedule Activity Selector */}
          <div className="space-y-1.5">
            <label htmlFor="target-activity-select" className="font-bold text-gray-800 block">
              Target Schedule Activity <span className="text-red-500">*</span>
            </label>
            {isLoadingActivities ? (
              <p className="text-gray-400 italic">Loading project schedule activities…</p>
            ) : (
              <select
                id="target-activity-select"
                value={selectedActivityId}
                onChange={(e) => setSelectedActivityId(e.target.value)}
                disabled={isSubmitting}
                className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 bg-white focus:ring-2 focus:ring-blue-500 outline-none"
              >
                {/* Ensure initial activity is listed if not in loaded list */}
                {selectedActivityId && !activities.some((a) => a.id === selectedActivityId) && (
                  <option value={selectedActivityId}>
                    {initialActivityName || 'Current Recommended Activity'}
                  </option>
                )}
                {activities.map((act) => (
                  <option key={act.id} value={act.id}>
                    {act.activity_code} — {act.name} {act.discipline ? `(${act.discipline})` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Quantity & Unit Row */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="modify-quantity" className="font-bold text-gray-800 block">
                Actual Quantity
              </label>
              <input
                id="modify-quantity"
                type="number"
                step="any"
                min="0"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                disabled={isSubmitting}
                placeholder="e.g. 15.5"
                className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="modify-unit" className="font-bold text-gray-800 block">
                Unit of Measure
              </label>
              <input
                id="modify-unit"
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                disabled={isSubmitting}
                placeholder="e.g. tons, spools, LF"
                className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          {/* Actual Work Date */}
          <div className="space-y-1.5">
            <label htmlFor="modify-date" className="font-bold text-gray-800 block">
              Actual Work Date <span className="text-red-500">*</span>
            </label>
            <input
              id="modify-date"
              type="date"
              value={dateVal}
              onChange={(e) => setDateVal(e.target.value)}
              disabled={isSubmitting}
              className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          {/* Planner Notes */}
          <div className="space-y-1.5">
            <label htmlFor="modify-notes" className="font-bold text-gray-800 block">
              Planner Notes / Clarification
            </label>
            <textarea
              id="modify-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={isSubmitting}
              placeholder="Explain why the recommendation was modified before approval..."
              className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-blue-500 outline-none resize-none"
            />
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-100">
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
              disabled={isSubmitting}
              className="bg-blue-700 hover:bg-blue-800 text-white font-semibold text-xs"
            >
              {isSubmitting ? 'Saving changes…' : 'Save & Approve Changes'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
