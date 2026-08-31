/**
 * Activity Risk Register Table — SiteSync AI Phase 9.6.
 * Displays itemized schedule activity risk scores, discrete severity levels,
 * active canonical risk taxonomy categories, and triggers Downstream Impact drawer.
 */

import { Button } from '@/components/ui/button'
import type { ActivityRiskAssessment, RiskCategory, RiskSeverityLevel } from '../types'

interface RiskActivityTableProps {
  items: ActivityRiskAssessment[]
  total: number
  limit: number
  offset: number
  isLoading?: boolean
  onPageChange: (newOffset: number) => void
  onViewImpact: (activityId: string) => void
}

const SEVERITY_BADGES: Record<RiskSeverityLevel, { label: string; style: string }> = {
  critical: { label: 'CRITICAL', style: 'bg-rose-100 text-rose-800 border-rose-300' },
  high: { label: 'HIGH', style: 'bg-amber-100 text-amber-800 border-amber-300' },
  medium: { label: 'MEDIUM', style: 'bg-yellow-100 text-yellow-800 border-yellow-300' },
  low: { label: 'LOW', style: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
}

const CATEGORY_LABELS: Record<RiskCategory, { label: string; style: string }> = {
  critical_path_delay: { label: 'Critical Path Delay', style: 'bg-rose-50 text-rose-700 border-rose-200' },
  float_erosion: { label: 'Float Erosion', style: 'bg-amber-50 text-amber-700 border-amber-200' },
  downstream_bottleneck: { label: 'Downstream Bottleneck', style: 'bg-orange-50 text-orange-700 border-orange-200' },
  predecessor_blocker: { label: 'Predecessor Blocker', style: 'bg-purple-50 text-purple-700 border-purple-200' },
  unquantified_milestone_lag: { label: 'Milestone Lag', style: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  unit_mismatch_exposure: { label: 'Unit Mismatch Exposure', style: 'bg-slate-50 text-slate-700 border-slate-200' },
}

export function RiskActivityTable({
  items,
  total,
  limit,
  offset,
  isLoading,
  onPageChange,
  onViewImpact,
}: RiskActivityTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm" data-testid="risk-table-loading">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-12 text-center shadow-sm">
        <p className="text-sm font-medium text-gray-900">No activity risk records found.</p>
        <p className="text-xs text-gray-500 mt-1">
          Adjust filter parameters or verify that activities exist in the project schedule baseline.
        </p>
      </div>
    )
  }

  const startIdx = offset + 1
  const endIdx = Math.min(offset + limit, total)
  const hasPrev = offset > 0
  const hasNext = offset + limit < total

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden space-y-0">
      {/* Table Title Bar */}
      <div className="px-5 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-gray-50/50">
        <div>
          <h3 className="text-sm font-bold text-gray-900 tracking-tight">
            Activity Risk Register
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Transparent composite scoring [0–100] and 6-category risk taxonomy assessments.
          </p>
        </div>
        <div className="text-xs text-gray-500">
          Showing <strong className="text-gray-900">{startIdx}</strong> to{' '}
          <strong className="text-gray-900">{endIdx}</strong> of{' '}
          <strong className="text-gray-900">{total}</strong> activities
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-xs text-left" aria-label="Activity Risk Register">
          <thead className="bg-gray-50 text-gray-600 font-semibold">
            <tr>
              <th scope="col" className="py-3 px-4">Code</th>
              <th scope="col" className="py-3 px-4">Activity Name</th>
              <th scope="col" className="py-3 px-3">Discipline</th>
              <th scope="col" className="py-3 px-3 text-center">Severity</th>
              <th scope="col" className="py-3 px-3 text-center">Risk Score</th>
              <th scope="col" className="py-3 px-4">Active Categories</th>
              <th scope="col" className="py-3 px-3 text-center">Total Float</th>
              <th scope="col" className="py-3 px-3 text-center">Date Variance</th>
              <th scope="col" className="py-3 px-3">Status</th>
              <th scope="col" className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {items.map((act) => {
              const sevBadge = SEVERITY_BADGES[act.severity] || SEVERITY_BADGES.low
              const tf = act.total_float
              const dVar = act.date_variance_days

              return (
                <tr key={act.activity_id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-gray-900 whitespace-nowrap">
                    {act.activity_code}
                  </td>
                  <td className="py-3 px-4 text-gray-800 font-medium min-w-[200px]">
                    {act.name}
                    {act.wbs_code && (
                      <span className="block text-[10px] text-gray-400 font-mono mt-0.5">
                        WBS: {act.wbs_code}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap">
                    {act.discipline || '—'}
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <span
                      role="status"
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold border ${sevBadge.style}`}
                    >
                      {sevBadge.label}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <div className="inline-flex items-center gap-1.5">
                      <span
                        className={`font-mono font-bold px-1.5 py-0.5 rounded text-xs ${
                          act.risk_score >= 70
                            ? 'text-rose-700 bg-rose-50 border border-rose-200'
                            : act.risk_score >= 40
                            ? 'text-amber-700 bg-amber-50 border border-amber-200'
                            : 'text-gray-700 bg-gray-50 border border-gray-200'
                        }`}
                      >
                        {act.risk_score}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1 max-w-xs">
                      {act.categories.length > 0 ? (
                        act.categories.map((cat) => {
                          const catInfo = CATEGORY_LABELS[cat]
                          return (
                            <span
                              key={cat}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                                catInfo?.style || 'bg-gray-50 text-gray-600'
                              }`}
                            >
                              {catInfo?.label || cat}
                            </span>
                          )
                        })
                      ) : (
                        <span className="text-[10px] text-gray-400">None</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap font-mono text-xs">
                    {tf !== null && tf !== undefined ? (
                      <span className={tf <= 0 ? 'text-rose-700 font-bold' : 'text-gray-700'}>
                        {tf}d
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap font-mono text-xs">
                    {dVar !== null && dVar !== undefined ? (
                      <span className={dVar > 0 ? 'text-rose-700 font-bold' : dVar < 0 ? 'text-emerald-700 font-medium' : 'text-gray-700'}>
                        {dVar > 0 ? `+${dVar}d` : `${dVar}d`}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap capitalize">
                    {act.variance_status ? act.variance_status.replace('_', ' ') : '—'}
                  </td>
                  <td className="py-3 px-4 text-right whitespace-nowrap">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onViewImpact(act.activity_id)}
                      className="text-xs h-7 px-2.5 text-blue-700 border-blue-200 hover:bg-blue-50"
                    >
                      View Impact
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="px-5 py-3 border-t border-gray-200 flex items-center justify-between bg-gray-50/50">
        <span className="text-xs text-gray-500">
          Page size: {limit}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            className="text-xs h-7"
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => onPageChange(offset + limit)}
            className="text-xs h-7"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
