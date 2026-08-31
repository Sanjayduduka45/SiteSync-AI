/**
 * VarianceDashboardPage — Primary Plan vs Actual construction intelligence dashboard.
 * Features:
 *   - Executive KPI summary cards & homogeneous physical scope rollups
 *   - Multi-factor filtering (WBS, Discipline, Variance Status, Date Range)
 *   - Itemized activity plan vs actual variance table with server-side pagination
 *   - WBS tier rollups aggregated strictly across homogeneous units
 * Strictly read-only, factual, and backed by Phase 8.2 backend APIs.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProject } from '@/features/projects/useProject'
import { Button } from '@/components/ui/button'
import {
  getVarianceActivities,
  getVarianceSummary,
  getVarianceWbs,
  formatVarianceError,
} from '@/features/variance/api'
import type { ActivityVarianceStatus, VarianceFilterParams } from '@/features/variance/types'
import { ProjectVarianceSummaryCards } from '@/features/variance/components/ProjectVarianceSummaryCards'
import { ActivityVarianceTable } from '@/features/variance/components/ActivityVarianceTable'
import { WbsRollupTable } from '@/features/variance/components/WbsRollupTable'
import { ExportDropdown } from '@/features/exports/components/ExportDropdown'

const PAGE_SIZE = 50

export default function VarianceDashboardPage() {
  const { selectedProjectId } = useProject()

  // Filter state
  const [wbsCode, setWbsCode] = useState('')
  const [discipline, setDiscipline] = useState('')
  const [varianceStatus, setVarianceStatus] = useState<ActivityVarianceStatus | 'all'>('all')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [offset, setOffset] = useState(0)

  // Date range validation
  const isDateRangeInvalid = Boolean(fromDate && toDate && fromDate > toDate)

  // Active query filters object
  const activeFilters: VarianceFilterParams = {
    limit: PAGE_SIZE,
    offset,
    wbs_code: wbsCode.trim() || undefined,
    discipline: discipline.trim() || undefined,
    variance_status: varianceStatus !== 'all' ? varianceStatus : undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
  }

  // 1. Summary Query
  const summaryQuery = useQuery({
    queryKey: ['variance-summary', selectedProjectId],
    queryFn: () => getVarianceSummary(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  // 2. Activities Query
  const activitiesQuery = useQuery({
    queryKey: ['variance-activities', selectedProjectId, activeFilters],
    queryFn: () => getVarianceActivities(selectedProjectId!, activeFilters),
    enabled: Boolean(selectedProjectId) && !isDateRangeInvalid,
  })

  // 3. WBS Rollups Query
  const wbsQuery = useQuery({
    queryKey: ['variance-wbs', selectedProjectId],
    queryFn: () => getVarianceWbs(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  const handleClearFilters = () => {
    setWbsCode('')
    setDiscipline('')
    setVarianceStatus('all')
    setFromDate('')
    setToDate('')
    setOffset(0)
  }

  const handleFilterChange = (setter: (val: any) => void, val: any) => {
    setter(val)
    setOffset(0)
  }

  if (!selectedProjectId) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
        <p className="text-sm font-medium text-gray-900">No project selected.</p>
        <p className="text-xs text-gray-500 mt-1">
          Please select a project from the top navigation bar to view Plan vs Actual variance metrics.
        </p>
      </div>
    )
  }

  const error = summaryQuery.error || activitiesQuery.error || wbsQuery.error

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-5 w-2 bg-amber-600 rounded-sm" />
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Plan vs Actual</h1>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            Human-verified construction progress intelligence and mathematical variance analysis.
          </p>
        </div>

        {selectedProjectId && (
          <ExportDropdown
            projectId={selectedProjectId}
            dataset="variance"
            datasetLabel="Export Variance"
          />
        )}
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-lg text-sm">
          <strong>Error: </strong> {formatVarianceError(error)}
        </div>
      )}

      {/* 1. Summary KPI Cards & Unit Rollups */}
      <ProjectVarianceSummaryCards
        summary={summaryQuery.data}
        isLoading={summaryQuery.isLoading}
      />

      {/* 2. Filter Bar */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h2 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Filter Activities
          </h2>
          {(wbsCode || discipline || varianceStatus !== 'all' || fromDate || toDate) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearFilters}
              className="text-xs text-gray-500 hover:text-gray-900 self-start sm:self-auto h-7 px-2"
            >
              Clear Filters
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* WBS Filter */}
          <div>
            <label htmlFor="filter-wbs" className="block text-xs font-medium text-gray-600 mb-1">
              WBS Code
            </label>
            <input
              id="filter-wbs"
              type="text"
              placeholder="e.g. 1.2"
              value={wbsCode}
              onChange={(e) => handleFilterChange(setWbsCode, e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          {/* Discipline Filter */}
          <div>
            <label htmlFor="filter-discipline" className="block text-xs font-medium text-gray-600 mb-1">
              Discipline
            </label>
            <input
              id="filter-discipline"
              type="text"
              placeholder="e.g. Piping, Civil"
              value={discipline}
              onChange={(e) => handleFilterChange(setDiscipline, e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          {/* Variance Status Filter */}
          <div>
            <label htmlFor="filter-status" className="block text-xs font-medium text-gray-600 mb-1">
              Status
            </label>
            <select
              id="filter-status"
              value={varianceStatus}
              onChange={(e) => handleFilterChange(setVarianceStatus, e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="all">All Statuses</option>
              <option value="not_started">Not Started</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="over_delivered">Over Delivered</option>
              <option value="unquantified">Unquantified</option>
              <option value="unit_mismatch">Unit Mismatch</option>
            </select>
          </div>

          {/* From Date Filter */}
          <div>
            <label htmlFor="filter-from-date" className="block text-xs font-medium text-gray-600 mb-1">
              From Actual Date
            </label>
            <input
              id="filter-from-date"
              type="date"
              value={fromDate}
              onChange={(e) => handleFilterChange(setFromDate, e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-md px-2 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          {/* To Date Filter */}
          <div>
            <label htmlFor="filter-to-date" className="block text-xs font-medium text-gray-600 mb-1">
              To Actual Date
            </label>
            <input
              id="filter-to-date"
              type="date"
              value={toDate}
              onChange={(e) => handleFilterChange(setToDate, e.target.value)}
              className="w-full bg-white border border-gray-300 rounded-md px-2 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
        </div>

        {/* Date Validation Alert */}
        {isDateRangeInvalid && (
          <p className="text-xs font-semibold text-rose-600" role="alert">
            From date must be on or before To date.
          </p>
        )}
      </div>

      {/* 3. Activity Variance Table */}
      <ActivityVarianceTable
        items={activitiesQuery.data?.items ?? []}
        total={activitiesQuery.data?.total ?? 0}
        limit={PAGE_SIZE}
        offset={offset}
        isLoading={activitiesQuery.isLoading}
        onPageChange={setOffset}
      />

      {/* 4. WBS Rollups */}
      <WbsRollupTable
        wbsItems={wbsQuery.data?.items ?? []}
        isLoading={wbsQuery.isLoading}
      />
    </div>
  )
}
