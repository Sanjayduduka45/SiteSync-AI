/**
 * 2D Risk Heatmap Matrix — SiteSync AI Phase 9.6 (ADR-018).
 * Visualizes activity concentration across Float Severity / Risk Severity (X-axis)
 * and Discipline / WBS (Y-axis) using authoritative backend data.
 * Pure presentation; no client-side risk formula generation.
 */

import { useMemo } from 'react'
import type { ActivityRiskAssessment, RiskSeverityLevel } from '../types'

interface RiskHeatmapProps {
  activities?: ActivityRiskAssessment[]
  isLoading?: boolean
  onSelectCell?: (severity?: RiskSeverityLevel, discipline?: string) => void
}

const SEVERITY_COLUMNS: { key: RiskSeverityLevel; label: string; subLabel: string; bg: string }[] = [
  { key: 'critical', label: 'Critical', subLabel: 'TF ≤ 0', bg: 'bg-rose-50 hover:bg-rose-100 text-rose-900 border-rose-200' },
  { key: 'high', label: 'Near-Critical', subLabel: '1–3d Float', bg: 'bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-200' },
  { key: 'medium', label: 'Moderate', subLabel: '4–7d Float', bg: 'bg-yellow-50 hover:bg-yellow-100 text-yellow-900 border-yellow-200' },
  { key: 'low', label: 'Safe', subLabel: '> 7d Float', bg: 'bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border-emerald-200' },
]

export function RiskHeatmap({ activities = [], isLoading, onSelectCell }: RiskHeatmapProps) {
  // Extract distinct trade disciplines
  const disciplines = useMemo(() => {
    const set = new Set<string>()
    for (const act of activities) {
      if (act.discipline && act.discipline.trim()) {
        set.add(act.discipline.trim())
      }
    }
    const list = Array.from(set).sort()
    return list.length > 0 ? list : ['General']
  }, [activities])

  // Aggregate matrix counts: [discipline][severity] -> count
  const matrix = useMemo(() => {
    const counts: Record<string, Record<RiskSeverityLevel, number>> = {}
    for (const d of disciplines) {
      counts[d] = { critical: 0, high: 0, medium: 0, low: 0 }
    }

    for (const act of activities) {
      const disc = (act.discipline && act.discipline.trim()) || 'General'
      const sev = act.severity
      if (!counts[disc]) {
        counts[disc] = { critical: 0, high: 0, medium: 0, low: 0 }
      }
      if (counts[disc][sev] !== undefined) {
        counts[disc][sev] += 1
      }
    }
    return counts
  }, [activities, disciplines])

  if (isLoading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm" data-testid="risk-heatmap-loading">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
        <div className="h-32 bg-gray-100 rounded animate-pulse" />
      </div>
    )
  }

  if (activities.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm text-center">
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
          2D Risk & Float Exposure Heatmap
        </h3>
        <p className="text-xs text-gray-500">No activity data available to generate heatmap matrix.</p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">
            2D Risk & Float Exposure Matrix (ADR-018)
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Activity concentration across Float Severity (X-axis) and Trade Discipline (Y-axis). Click any cell to filter the register.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-xs text-left border-collapse" aria-label="Risk Heatmap Matrix">
          <thead>
            <tr>
              <th scope="col" className="p-2.5 font-semibold text-gray-600 bg-gray-50 border border-gray-200 w-44">
                Discipline \ Float Band
              </th>
              {SEVERITY_COLUMNS.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className="p-2.5 font-semibold text-center text-gray-700 bg-gray-50 border border-gray-200"
                >
                  <div className="font-bold">{col.label}</div>
                  <div className="text-[10px] text-gray-400 font-normal">{col.subLabel}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {disciplines.map((disc) => (
              <tr key={disc} className="hover:bg-gray-50/50">
                <th scope="row" className="p-2.5 font-medium text-gray-900 bg-gray-50/70 border border-gray-200 whitespace-nowrap">
                  {disc}
                </th>
                {SEVERITY_COLUMNS.map((col) => {
                  const count = matrix[disc]?.[col.key] ?? 0
                  return (
                    <td
                      key={col.key}
                      className="p-1 border border-gray-200 text-center"
                    >
                      <button
                        type="button"
                        onClick={() => onSelectCell?.(col.key, disc === 'General' ? undefined : disc)}
                        className={`w-full py-2 px-3 rounded text-xs font-bold transition-all border ${
                          count > 0 ? col.bg : 'bg-gray-50/50 text-gray-400 border-gray-100 hover:bg-gray-100'
                        }`}
                        aria-label={`${count} ${col.label} activities in ${disc}`}
                      >
                        {count}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
