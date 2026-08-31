/**
 * ProjectVarianceSummaryCards — High-level KPI summary cards and unit rollups.
 * Visualizes backend Phase 8.2 ProjectVarianceSummary response.
 * Follows ADR-012: Never computes an unweighted average of activity percentages.
 */

import type { ProjectVarianceSummary } from '../types'

interface ProjectVarianceSummaryCardsProps {
  summary?: ProjectVarianceSummary | null
  isLoading?: boolean
}

export function ProjectVarianceSummaryCards({
  summary,
  isLoading = false,
}: ProjectVarianceSummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 animate-pulse">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white p-4 rounded-lg border border-gray-200 h-24" />
        ))}
      </div>
    )
  }

  if (!summary) return null

  const overallProgressDisplay =
    summary.overall_progress_percent !== null && summary.overall_progress_percent !== undefined
      ? `${summary.overall_progress_percent.toFixed(1)}%`
      : summary.unit_rollups.length > 1
      ? 'Multiple units'
      : '—'

  return (
    <div className="space-y-6">
      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Total Activities */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Total Activities
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{summary.total_activities}</p>
        </div>

        {/* Verified Progress */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            With Verified Progress
          </p>
          <p className="mt-1 text-2xl font-bold text-blue-600">
            {summary.activities_with_progress}
          </p>
        </div>

        {/* Completed */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Completed</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">
            {summary.completed_activities}
          </p>
        </div>

        {/* In Progress */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">In Progress</p>
          <p className="mt-1 text-2xl font-bold text-amber-600">
            {summary.in_progress_activities}
          </p>
        </div>

        {/* Not Started */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Not Started</p>
          <p className="mt-1 text-2xl font-bold text-gray-500">
            {summary.not_started_activities}
          </p>
        </div>

        {/* Overall Progress */}
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Overall Progress
          </p>
          <p className="mt-1 text-2xl font-bold text-gray-900" title={overallProgressDisplay}>
            {overallProgressDisplay}
          </p>
        </div>
      </div>

      {/* Flagged Count Alert if > 0 */}
      {summary.flagged_variance_count > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-800 flex items-center justify-between">
          <span>
            <strong>{summary.flagged_variance_count}</strong> activities flagged with significant
            variance.
          </span>
        </div>
      )}

      {/* Homogeneous Unit Rollups Breakdown */}
      {summary.unit_rollups.length > 0 && (
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
            Physical Scope Rollups by Unit
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {summary.unit_rollups.map((u) => {
              const sign = u.quantity_variance > 0 ? '+' : ''
              const formattedVar = `${sign}${u.quantity_variance.toLocaleString()} ${u.unit}`
              const varDesc =
                u.quantity_variance > 0
                  ? 'over plan'
                  : u.quantity_variance < 0
                  ? 'under plan'
                  : 'on plan'

              return (
                <div
                  key={u.unit}
                  className="bg-gray-50 p-3 rounded-md border border-gray-200 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase text-gray-700">{u.unit}</span>
                    <span className="text-xs font-semibold text-gray-900">
                      {u.progress_percent !== null && u.progress_percent !== undefined
                        ? `${u.progress_percent.toFixed(1)}%`
                        : '—'}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600 space-y-0.5 pt-1">
                    <div>Planned: {u.planned_total.toLocaleString()} {u.unit}</div>
                    <div>Actual: {u.actual_total.toLocaleString()} {u.unit}</div>
                    <div
                      className={
                        u.quantity_variance < 0
                          ? 'text-rose-600 font-medium'
                          : u.quantity_variance > 0
                          ? 'text-amber-700 font-medium'
                          : 'text-gray-600 font-medium'
                      }
                    >
                      Variance: {formattedVar} ({varDesc})
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
