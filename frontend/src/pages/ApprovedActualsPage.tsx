/**
 * ApprovedActualsPage — Official human-verified construction progress actuals interface.
 * Strictly read-only listing with server-side pagination, date filtering,
 * schedule activity filtering, and activity enrichment.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { formatApprovedActualsError, getApprovedActuals } from '@/features/decisions/api'
import { ApprovedActualsTable } from '@/features/decisions/components/ApprovedActualsTable'
import { useProject } from '@/features/projects/useProject'
import { getScheduleActivities } from '@/features/schedules/api'
import type { ScheduleActivity } from '@/features/schedules/types'
import { ExportDropdown } from '@/features/exports/components/ExportDropdown'

const PAGE_SIZE = 50

export default function ApprovedActualsPage() {
  const { selectedProjectId, selectedProject } = useProject()

  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [scheduleActivityId, setScheduleActivityId] = useState('')
  const [offset, setOffset] = useState(0)
  const [filterValidationError, setFilterValidationError] = useState<string | null>(null)

  // Validate dates client-side before sending
  const isDateRangeInvalid = Boolean(fromDate && toDate && fromDate > toDate)

  // Query baseline schedule activities for enrichment and filter dropdown
  const { data: scheduleData } = useQuery({
    queryKey: ['schedule-activities', selectedProjectId],
    queryFn: () => {
      if (!selectedProjectId) throw new Error('No project selected')
      return getScheduleActivities(selectedProjectId, 100, 0)
    },
    enabled: !!selectedProjectId,
  })

  const activitiesMap: Record<string, ScheduleActivity> = {}
  if (scheduleData?.items) {
    for (const act of scheduleData.items) {
      activitiesMap[act.id] = act
    }
  }

  // Query approved actuals
  const {
    data: actualsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'approved-actuals',
      selectedProjectId,
      {
        limit: PAGE_SIZE,
        offset,
        scheduleActivityId: scheduleActivityId || undefined,
        fromDate: fromDate || undefined,
        toDate: toDate || undefined,
      },
    ],
    queryFn: () => {
      if (!selectedProjectId) throw new Error('No project selected')
      if (isDateRangeInvalid) {
        throw new Error('From date must be on or before To date.')
      }
      return getApprovedActuals(
        selectedProjectId,
        PAGE_SIZE,
        offset,
        scheduleActivityId || undefined,
        fromDate || undefined,
        toDate || undefined
      )
    },
    enabled: !!selectedProjectId && !isDateRangeInvalid,
  })

  const handleFromDateChange = (val: string) => {
    setFromDate(val)
    setOffset(0)
    if (toDate && val && val > toDate) {
      setFilterValidationError('From date must be on or before To date.')
    } else {
      setFilterValidationError(null)
    }
  }

  const handleToDateChange = (val: string) => {
    setToDate(val)
    setOffset(0)
    if (fromDate && val && fromDate > val) {
      setFilterValidationError('From date must be on or before To date.')
    } else {
      setFilterValidationError(null)
    }
  }

  const handleActivityChange = (val: string) => {
    setScheduleActivityId(val)
    setOffset(0)
  }

  const handleClearFilters = () => {
    setFromDate('')
    setToDate('')
    setScheduleActivityId('')
    setOffset(0)
    setFilterValidationError(null)
  }

  const total = actualsData?.total ?? 0
  const items = actualsData?.items ?? []
  const hasActiveFilters = Boolean(fromDate || toDate || scheduleActivityId)

  // Pagination calculation
  const startIdx = total === 0 ? 0 : offset + 1
  const endIdx = Math.min(offset + PAGE_SIZE, total)
  const canPrev = offset > 0
  const canNext = offset + PAGE_SIZE < total

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-gray-900 tracking-tight">Approved Actuals</span>
            <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
              Official verified progress records
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1 max-w-2xl">
            Human-verified field progress approved through SiteSync AI's planner review workflow.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {selectedProjectId && (
            <ExportDropdown
              projectId={selectedProjectId}
              dataset="approved_actuals"
              datasetLabel="Export Actuals"
            />
          )}

          {selectedProject && (
            <div className="text-right sm:block hidden">
              <span className="text-xs font-semibold text-gray-700 block">
                {selectedProject.projectName}
              </span>
              <span className="text-[11px] font-mono text-gray-400">
                {selectedProject.projectCode}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-2xs space-y-3">
        <div className="flex flex-wrap items-end gap-3 text-xs">
          {/* Schedule Activity Filter */}
          <div className="space-y-1 min-w-[200px] flex-1">
            <label htmlFor="filter-activity" className="font-semibold text-gray-700 block text-[11px]">
              Filter by Schedule Activity
            </label>
            <select
              id="filter-activity"
              value={scheduleActivityId}
              onChange={(e) => handleActivityChange(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-2 text-xs text-gray-900 bg-white focus:ring-2 focus:ring-gray-900 outline-none"
            >
              <option value="">All Baseline Activities</option>
              {scheduleData?.items?.map((act) => (
                <option key={act.id} value={act.id}>
                  {act.activity_code} — {act.name} {act.discipline ? `(${act.discipline})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Date From */}
          <div className="space-y-1">
            <label htmlFor="filter-from-date" className="font-semibold text-gray-700 block text-[11px]">
              Date From
            </label>
            <input
              id="filter-from-date"
              type="date"
              value={fromDate}
              onChange={(e) => handleFromDateChange(e.target.value)}
              className="border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-gray-900 outline-none"
            />
          </div>

          {/* Date To */}
          <div className="space-y-1">
            <label htmlFor="filter-to-date" className="font-semibold text-gray-700 block text-[11px]">
              Date To
            </label>
            <input
              id="filter-to-date"
              type="date"
              value={toDate}
              onChange={(e) => handleToDateChange(e.target.value)}
              className="border border-gray-300 rounded-lg p-2 text-xs text-gray-900 focus:ring-2 focus:ring-gray-900 outline-none"
            />
          </div>

          {/* Clear Button */}
          {hasActiveFilters && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearFilters}
              className="h-8 px-3 text-xs text-gray-600 hover:text-gray-900 border-gray-300"
            >
              Clear Filters
            </Button>
          )}
        </div>

        {/* Date Validation Alert */}
        {(filterValidationError || isDateRangeInvalid) && (
          <div className="bg-red-50 border border-red-200 p-2.5 rounded-lg text-xs text-red-700 font-medium" role="alert">
            {filterValidationError || 'From date must be on or before To date.'}
          </div>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-xl text-xs text-red-800 space-y-2" role="alert">
          <p className="font-bold">Error loading approved actuals</p>
          <p>{formatApprovedActualsError(error)}</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => refetch()}
            className="text-xs bg-white text-red-700 border-red-300 hover:bg-red-50"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Approved Actuals Table */}
      <ApprovedActualsTable
        items={items}
        activitiesMap={activitiesMap}
        isLoading={isLoading}
      />

      {/* Pagination Bar */}
      {total > 0 && (
        <div className="flex items-center justify-between bg-white px-4 py-3 border border-gray-200 rounded-xl shadow-2xs text-xs">
          <span className="text-gray-600">
            {`Showing ${startIdx}–${endIdx} of ${total}`}
          </span>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
              disabled={!canPrev || isLoading}
              className="h-7 px-2.5 text-xs text-gray-700 border-gray-300 disabled:opacity-40"
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
              disabled={!canNext || isLoading}
              className="h-7 px-2.5 text-xs text-gray-700 border-gray-300 disabled:opacity-40"
            >
              Next
            </Button>
          </div>
        </div>
      )}

    </div>
  )
}
