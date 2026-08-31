/**
 * Critical Path Method (CPM) Schedule Table — SiteSync AI Phase 9.6.
 * Displays calculated activity schedule nodes, forward/backward pass dates,
 * exact total/free float values (including negative float), and critical path flags.
 */

import type { CPMActivityNodeResponse } from '../types'

interface CriticalPathTableProps {
  activities?: CPMActivityNodeResponse[]
  isLoading?: boolean
  totalActivities?: number
  criticalCount?: number
}

export function CriticalPathTable({
  activities = [],
  isLoading,
  totalActivities = 0,
  criticalCount = 0,
}: CriticalPathTableProps) {
  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm" data-testid="cpm-table-loading">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (activities.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-12 text-center shadow-sm">
        <p className="text-sm font-medium text-gray-900">No Critical Path schedule data found.</p>
        <p className="text-xs text-gray-500 mt-1">
          Ensure schedule baseline activities and dependencies are configured for this project.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
      {/* Table Header / Subtitle */}
      <div className="px-5 py-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-gray-50/50">
        <div>
          <h3 className="text-sm font-bold text-gray-900 tracking-tight">
            Critical Path Schedule Network
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Topologically ordered schedule network with exact Early/Late dates and float preservation.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-500">
            Total Activities: <strong className="text-gray-900">{totalActivities}</strong>
          </span>
          <span className="text-rose-700 font-semibold bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
            Critical: {criticalCount}
          </span>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-xs text-left" aria-label="Critical Path Network Schedule">
          <thead className="bg-gray-50 text-gray-600 font-semibold">
            <tr>
              <th scope="col" className="py-3 px-4">Code</th>
              <th scope="col" className="py-3 px-4">Activity Name</th>
              <th scope="col" className="py-3 px-4">Discipline</th>
              <th scope="col" className="py-3 px-3 text-center">Duration</th>
              <th scope="col" className="py-3 px-3">Early Start</th>
              <th scope="col" className="py-3 px-3">Early Finish</th>
              <th scope="col" className="py-3 px-3">Late Start</th>
              <th scope="col" className="py-3 px-3">Late Finish</th>
              <th scope="col" className="py-3 px-3 text-center">Total Float</th>
              <th scope="col" className="py-3 px-3 text-center">Free Float</th>
              <th scope="col" className="py-3 px-4 text-center">Criticality</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {activities.map((node) => {
              const isCrit = node.is_critical
              const tf = node.total_float_days
              const ff = node.free_float_days

              return (
                <tr
                  key={node.activity_id}
                  className={`hover:bg-gray-50 transition-colors ${
                    isCrit ? 'bg-rose-50/20 font-medium' : ''
                  }`}
                >
                  <td className="py-3 px-4 font-mono font-bold text-gray-900 whitespace-nowrap">
                    {node.activity_code}
                  </td>
                  <td className="py-3 px-4 text-gray-800 font-medium min-w-[200px]">
                    {node.name}
                    {node.wbs_code && (
                      <span className="block text-[10px] text-gray-400 font-mono mt-0.5">
                        WBS: {node.wbs_code}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-gray-600 whitespace-nowrap">
                    {node.discipline || '—'}
                  </td>
                  <td className="py-3 px-3 text-center text-gray-700 whitespace-nowrap">
                    {node.duration_days}d
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap">
                    {node.early_start || '—'}
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap">
                    {node.early_finish || '—'}
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap">
                    {node.late_start || '—'}
                  </td>
                  <td className="py-3 px-3 text-gray-600 whitespace-nowrap">
                    {node.late_finish || '—'}
                  </td>
                  <td className="py-3 px-3 text-center whitespace-nowrap">
                    <span
                      className={`font-mono font-bold px-1.5 py-0.5 rounded text-xs ${
                        tf !== null && tf <= 0
                          ? 'text-rose-700 bg-rose-50 border border-rose-200'
                          : tf !== null && tf <= 3
                          ? 'text-amber-700 bg-amber-50 border border-amber-200'
                          : 'text-gray-700'
                      }`}
                    >
                      {tf !== null && tf !== undefined ? `${tf}d` : '—'}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center font-mono text-gray-700 whitespace-nowrap">
                    {ff !== null && ff !== undefined ? `${ff}d` : '—'}
                  </td>
                  <td className="py-3 px-4 text-center whitespace-nowrap">
                    {isCrit ? (
                      <span
                        role="status"
                        className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200"
                      >
                        CRITICAL
                      </span>
                    ) : (
                      <span
                        role="status"
                        className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-600 border border-gray-200"
                      >
                        Non-Critical
                      </span>
                    )}
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
