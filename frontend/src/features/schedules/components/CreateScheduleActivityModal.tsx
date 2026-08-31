/**
 * CreateScheduleActivityModal — Form dialog for adding baseline schedule activities.
 * Requires Planner or Admin role.
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { ScheduleActivityCreateInput } from '../types'

interface CreateScheduleActivityModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: ScheduleActivityCreateInput) => Promise<void>
  isSubmitting: boolean
}

export function CreateScheduleActivityModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}: CreateScheduleActivityModalProps) {
  const [activityCode, setActivityCode] = useState('')
  const [name, setName] = useState('')
  const [wbsCode, setWbsCode] = useState('')
  const [discipline, setDiscipline] = useState('')
  const [location, setLocation] = useState('')
  const [plannedStartDate, setPlannedStartDate] = useState('')
  const [plannedFinishDate, setPlannedFinishDate] = useState('')
  const [plannedQuantity, setPlannedQuantity] = useState('')
  const [plannedUnit, setPlannedUnit] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (!activityCode.trim()) {
      setValidationError('Activity code is required.')
      return
    }

    if (!name.trim()) {
      setValidationError('Activity name is required.')
      return
    }

    if (plannedStartDate && plannedFinishDate && plannedStartDate > plannedFinishDate) {
      setValidationError('Planned start date cannot be after planned finish date.')
      return
    }

    const payload: ScheduleActivityCreateInput = {
      activity_code: activityCode.trim(),
      name: name.trim(),
      wbs_code: wbsCode.trim() || undefined,
      discipline: discipline.trim() || undefined,
      location: location.trim() || undefined,
      planned_start_date: plannedStartDate || undefined,
      planned_finish_date: plannedFinishDate || undefined,
      planned_quantity: plannedQuantity ? parseFloat(plannedQuantity) : undefined,
      planned_unit: plannedUnit.trim() || undefined,
    }

    try {
      await onSubmit(payload)
      onClose()
    } catch (err: unknown) {
      setValidationError(err instanceof Error ? err.message : 'Failed to create schedule activity')
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 max-w-lg w-full overflow-hidden flex flex-col max-h-[90vh]">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
          <div>
            <h2 className="text-sm font-bold text-gray-900">Add Baseline Schedule Activity</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Enter schedule attributes for AI candidate matching
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-4 text-xs">
          {validationError && (
            <div className="bg-red-50 border border-red-200 p-3 rounded text-red-700 font-medium">
              {validationError}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label htmlFor="activityCode" className="font-semibold text-gray-700 block">
                Activity Code <span className="text-red-500">*</span>
              </label>
              <input
                id="activityCode"
                type="text"
                value={activityCode}
                onChange={(e) => setActivityCode(e.target.value)}
                placeholder="e.g. ACT-1040"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900 font-mono"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="wbsCode" className="font-semibold text-gray-700 block">
                WBS Code
              </label>
              <input
                id="wbsCode"
                type="text"
                value={wbsCode}
                onChange={(e) => setWbsCode(e.target.value)}
                placeholder="e.g. 1.2.4"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900 font-mono"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label htmlFor="name" className="font-semibold text-gray-700 block">
              Activity Name <span className="text-red-500">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Install Underground Chilled Water Supply Line"
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label htmlFor="discipline" className="font-semibold text-gray-700 block">
                Discipline / Trade
              </label>
              <input
                id="discipline"
                type="text"
                value={discipline}
                onChange={(e) => setDiscipline(e.target.value)}
                placeholder="e.g. Piping, Civil, Electrical"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="location" className="font-semibold text-gray-700 block">
                Physical Location
              </label>
              <input
                id="location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Rack 4 Level 2"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label htmlFor="plannedStartDate" className="font-semibold text-gray-700 block">
                Planned Start Date
              </label>
              <input
                id="plannedStartDate"
                type="date"
                value={plannedStartDate}
                onChange={(e) => setPlannedStartDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="plannedFinishDate" className="font-semibold text-gray-700 block">
                Planned Finish Date
              </label>
              <input
                id="plannedFinishDate"
                type="date"
                value={plannedFinishDate}
                onChange={(e) => setPlannedFinishDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label htmlFor="plannedQuantity" className="font-semibold text-gray-700 block">
                Planned Quantity
              </label>
              <input
                id="plannedQuantity"
                type="number"
                step="any"
                min="0"
                value={plannedQuantity}
                onChange={(e) => setPlannedQuantity(e.target.value)}
                placeholder="e.g. 500"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="plannedUnit" className="font-semibold text-gray-700 block">
                Planned Unit
              </label>
              <input
                id="plannedUnit"
                type="text"
                value={plannedUnit}
                onChange={(e) => setPlannedUnit(e.target.value)}
                placeholder="e.g. LF, m3, tons"
                className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-gray-900"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-gray-200 flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="bg-gray-900 text-white hover:bg-gray-800"
            >
              {isSubmitting ? 'Saving Activity…' : 'Save Activity'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
