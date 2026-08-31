/**
 * WbsRollupTable — WBS tier rollups aggregated across homogeneous units.
 * Follows ADR-012: Never computes an unweighted percentage average across activities.
 */

import type { WbsRollup } from '../types'

interface WbsRollupTableProps {
  wbsItems: WbsRollup[]
  isLoading?: boolean
}

export function WbsRollupTable({ wbsItems, isLoading = false }: WbsRollupTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/4 mb-4" />
        <div className="h-20 bg-gray-100 rounded" />
      </div>
    )
  }

  if (wbsItems.length === 0) {
    return null
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-base font-semibold text-gray-900">Work Breakdown Structure (WBS) Rollups</h2>
        <p className="text-xs text-gray-500">
          Physical quantities aggregated strictly across homogeneous units per WBS tier.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs" aria-label="WBS Rollups Table">
          <thead className="bg-gray-100 text-gray-700 uppercase font-semibold">
            <tr>
              <th scope="col" className="px-6 py-3">WBS Tier</th>
              <th scope="col" className="px-4 py-3">Unit</th>
              <th scope="col" className="px-4 py-3">Planned Total</th>
              <th scope="col" className="px-4 py-3">Actual Total</th>
              <th scope="col" className="px-4 py-3">Quantity Variance</th>
              <th scope="col" className="px-4 py-3">Progress %</th>
              <th scope="col" className="px-4 py-3 text-right">Activities</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {wbsItems.map((wbs) => {
              // If WBS has unit rollups, render a row for each unit
              if (wbs.unit_rollups.length > 0) {
                return wbs.unit_rollups.map((rollup, idx) => {
                  const sign = rollup.quantity_variance > 0 ? '+' : ''
                  const formattedVar = `${sign}${rollup.quantity_variance.toLocaleString()} ${rollup.unit}`
                  const varDesc =
                    rollup.quantity_variance > 0
                      ? 'over plan'
                      : rollup.quantity_variance < 0
                      ? 'under plan'
                      : 'on plan'

                  return (
                    <tr
                      key={`${wbs.wbs_code}-${rollup.unit}-${idx}`}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      {/* Show WBS Code only on first unit row if multi-unit */}
                      <td className="px-6 py-3 font-mono font-bold text-gray-900">
                        {idx === 0 ? wbs.wbs_code : `${wbs.wbs_code} (cont.)`}
                      </td>
                      <td className="px-4 py-3 font-semibold uppercase text-gray-700">
                        {rollup.unit}
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {rollup.planned_total.toLocaleString()} {rollup.unit}
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-900">
                        {rollup.actual_total.toLocaleString()} {rollup.unit}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`font-semibold ${
                            rollup.quantity_variance < 0
                              ? 'text-rose-600'
                              : rollup.quantity_variance > 0
                              ? 'text-amber-700'
                              : 'text-gray-700'
                          }`}
                        >
                          {formattedVar}
                        </span>{' '}
                        <span className="text-[11px] text-gray-500">({varDesc})</span>
                      </td>
                      <td className="px-4 py-3 font-bold text-gray-900">
                        {rollup.progress_percent !== null && rollup.progress_percent !== undefined
                          ? `${rollup.progress_percent.toFixed(1)}%`
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 font-medium">
                        {rollup.activity_count} / {wbs.total_activity_count}
                      </td>
                    </tr>
                  )
                })
              }

              // WBS has only unquantified or unassigned activities
              return (
                <tr key={wbs.wbs_code} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-3 font-mono font-bold text-gray-900">{wbs.wbs_code}</td>
                  <td className="px-4 py-3 text-gray-400">—</td>
                  <td className="px-4 py-3 text-gray-400">—</td>
                  <td className="px-4 py-3 text-gray-400">—</td>
                  <td className="px-4 py-3 text-gray-400">—</td>
                  <td className="px-4 py-3 text-gray-400">—</td>
                  <td className="px-4 py-3 text-right text-gray-600 font-medium">
                    {wbs.total_activity_count} (Unquantified)
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
