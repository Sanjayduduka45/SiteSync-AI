/**
 * ActivityVarianceTable — Detailed Plan vs Actual comparison table.
 * Strictly presents backend mathematical calculations and status classifications.
 * Visualizes quantity variance, progress percentage, date slippage, and status badges.
 */

import { Button } from '@/components/ui/button'
import type { ActivityVarianceItem } from '../types'
import { VarianceStatusBadge } from './VarianceStatusBadge'

interface ActivityVarianceTableProps {
  items: ActivityVarianceItem[]
  total: number
  limit: number
  offset: number
  isLoading?: boolean
  onPageChange: (newOffset: number) => void
}

export function ActivityVarianceTable({
  items,
  total,
  limit,
  offset,
  isLoading = false,
  onPageChange,
}: ActivityVarianceTableProps) {
  const currentPage = Math.floor(offset / limit) + 1
  const totalPages = Math.ceil(total / limit) || 1
  const startIdx = total === 0 ? 0 : offset + 1
  const endIdx = Math.min(offset + limit, total)

  const formatQuantityVariance = (item: ActivityVarianceItem) => {
    if (item.quantity_variance === null || item.quantity_variance === undefined) {
      return '—'
    }
    const unit = item.planned_unit || ''
    const sign = item.quantity_variance > 0 ? '+' : ''
    const formattedVal = `${sign}${item.quantity_variance.toLocaleString()} ${unit}`.trim()
    const desc =
      item.quantity_variance > 0
        ? `${Math.abs(item.quantity_variance).toLocaleString()} ${unit} over plan`
        : item.quantity_variance < 0
        ? `${Math.abs(item.quantity_variance).toLocaleString()} ${unit} under plan`
        : 'On plan'

    return (
      <div className="flex flex-col">
        <span
          className={`font-semibold ${
            item.quantity_variance < 0
              ? 'text-rose-600'
              : item.quantity_variance > 0
              ? 'text-amber-700'
              : 'text-gray-700'
          }`}
        >
          {formattedVal}
        </span>
        <span className="text-[11px] text-gray-500">{desc}</span>
      </div>
    )
  }

  const formatDateVariance = (item: ActivityVarianceItem) => {
    if (item.date_variance_days === null || item.date_variance_days === undefined) {
      return '—'
    }
    const days = item.date_variance_days
    if (days > 0) {
      return (
        <span className="text-rose-600 font-medium" title={`${days} days past planned finish`}>
          +{days} days Late
        </span>
      )
    }
    if (days < 0) {
      return (
        <span className="text-emerald-700 font-medium" title={`${Math.abs(days)} days ahead of planned finish`}>
          {days} days Early
        </span>
      )
    }
    return <span className="text-gray-700 font-medium">0 days On Time</span>
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      {/* Table Title and Pagination summary */}
      <div className="px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 bg-gray-50">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Activity Plan vs Actuals</h2>
          <p className="text-xs text-gray-500">
            Factual variance between baseline schedule and human-verified field actuals.
          </p>
        </div>
        <div className="text-xs text-gray-600 font-medium">
          Showing {startIdx}–{endIdx} of {total} activities
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs" aria-label="Activity Plan vs Actual Table">
          <thead className="bg-gray-100 text-gray-700 uppercase font-semibold">
            <tr>
              <th scope="col" className="px-4 py-3">Activity</th>
              <th scope="col" className="px-3 py-3">WBS</th>
              <th scope="col" className="px-3 py-3">Discipline</th>
              <th scope="col" className="px-3 py-3">Planned</th>
              <th scope="col" className="px-3 py-3">Actual (Verified)</th>
              <th scope="col" className="px-3 py-3">Progress %</th>
              <th scope="col" className="px-4 py-3">Quantity Variance</th>
              <th scope="col" className="px-3 py-3">Finish / Actual Date</th>
              <th scope="col" className="px-3 py-3">Date Variance</th>
              <th scope="col" className="px-4 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {isLoading ? (
              <tr>
                <td colSpan={10} className="px-4 py-12 text-center text-gray-400">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <div className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                    <span>Loading Plan vs Actual variance data...</span>
                  </div>
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-12 text-center text-gray-500">
                  <p className="text-sm font-medium text-gray-900">No schedule activities found.</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Import a baseline schedule or adjust your filter criteria to view variance metrics.
                  </p>
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.activity_id} className="hover:bg-gray-50 transition-colors">
                  {/* Activity Code & Name */}
                  <td className="px-4 py-3 max-w-[200px]">
                    <div className="font-semibold text-gray-900">{item.activity_code}</div>
                    <div className="text-gray-500 truncate" title={item.name}>
                      {item.name}
                    </div>
                  </td>

                  {/* WBS */}
                  <td className="px-3 py-3 font-mono text-gray-700">
                    {item.wbs_code || '—'}
                  </td>

                  {/* Discipline */}
                  <td className="px-3 py-3 text-gray-700">
                    {item.discipline || '—'}
                  </td>

                  {/* Planned Quantity */}
                  <td className="px-3 py-3 font-medium text-gray-900">
                    {item.planned_quantity !== null && item.planned_quantity !== undefined
                      ? `${item.planned_quantity.toLocaleString()} ${item.planned_unit || ''}`
                      : '—'}
                  </td>

                  {/* Actual Quantity */}
                  <td className="px-3 py-3 font-medium text-gray-900">
                    {item.actual_quantity_total !== null && item.actual_quantity_total !== undefined
                      ? `${item.actual_quantity_total.toLocaleString()} ${item.actual_unit || item.planned_unit || ''}`
                      : '—'}
                  </td>

                  {/* Progress % */}
                  <td className="px-3 py-3 font-bold text-gray-900">
                    {item.progress_percent !== null && item.progress_percent !== undefined
                      ? `${item.progress_percent.toFixed(1)}%`
                      : '—'}
                  </td>

                  {/* Quantity Variance */}
                  <td className="px-4 py-3">
                    {formatQuantityVariance(item)}
                  </td>

                  {/* Dates */}
                  <td className="px-3 py-3 text-gray-700 space-y-0.5">
                    <div>
                      <span className="text-[10px] text-gray-400 uppercase">Plan: </span>
                      {item.planned_finish_date || '—'}
                    </div>
                    <div>
                      <span className="text-[10px] text-gray-400 uppercase">Act: </span>
                      {item.latest_actual_date || '—'}
                    </div>
                  </td>

                  {/* Date Variance */}
                  <td className="px-3 py-3 whitespace-nowrap">
                    {formatDateVariance(item)}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3 text-center">
                    <VarianceStatusBadge status={item.variance_status} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between bg-gray-50">
        <span className="text-xs text-gray-500">
          Page {currentPage} of {totalPages}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0 || isLoading}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            className="text-xs"
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + limit >= total || isLoading}
            onClick={() => onPageChange(offset + limit)}
            className="text-xs"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
