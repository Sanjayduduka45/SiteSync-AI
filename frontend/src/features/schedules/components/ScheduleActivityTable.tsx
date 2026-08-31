/**
 * ScheduleActivityTable — Professional construction schedule activity grid.
 * Displays baseline activities with code, name, discipline, location, WBS, planned dates, and quantities.
 */

import type { ScheduleActivity } from '../types'

interface ScheduleActivityTableProps {
  activities: ScheduleActivity[]
  isLoading: boolean
}

export function ScheduleActivityTable({ activities, isLoading }: ScheduleActivityTableProps) {
  if (isLoading) {
    return (
      <div className="p-8 text-center bg-white rounded-lg border border-gray-200">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-2" />
        <p className="text-xs text-gray-500">Loading schedule activities…</p>
      </div>
    )
  }

  if (activities.length === 0) {
    return (
      <div className="p-12 text-center bg-white rounded-lg border border-gray-200 space-y-2">
        <div className="text-2xl">📅</div>
        <h3 className="text-sm font-semibold text-gray-900">No schedule activities yet</h3>
        <p className="text-xs text-gray-500 max-w-sm mx-auto">
          Create the project's baseline schedule to enable AI matching against field inputs.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-2xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 uppercase tracking-wider font-semibold">
            <tr>
              <th className="px-4 py-3">Activity Code</th>
              <th className="px-4 py-3">Activity Name</th>
              <th className="px-4 py-3">Discipline</th>
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">WBS</th>
              <th className="px-4 py-3">Planned Window</th>
              <th className="px-4 py-3 text-right">Planned Qty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-gray-800">
            {activities.map((act) => (
              <tr key={act.id} className="hover:bg-gray-50/70 transition-colors">
                <td className="px-4 py-3 font-mono font-bold text-gray-900 whitespace-nowrap">
                  {act.activity_code}
                </td>
                <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">
                  {act.name}
                </td>
                <td className="px-4 py-3">
                  {act.discipline ? (
                    <span className="inline-block text-[10px] font-bold uppercase px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded">
                      {act.discipline}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {act.location || <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 font-mono text-gray-500">
                  {act.wbs_code || <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {act.planned_start_date && act.planned_finish_date ? (
                    <span>
                      {act.planned_start_date} → {act.planned_finish_date}
                    </span>
                  ) : act.planned_start_date ? (
                    <span>From {act.planned_start_date}</span>
                  ) : act.planned_finish_date ? (
                    <span>By {act.planned_finish_date}</span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-medium text-gray-900 whitespace-nowrap">
                  {act.planned_quantity !== null && act.planned_quantity !== undefined ? (
                    <span>
                      {act.planned_quantity} {act.planned_unit || ''}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
