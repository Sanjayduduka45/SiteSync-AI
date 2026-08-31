/**
 * Executive Risk Summary Cards — SiteSync AI Phase 9.6.
 * Displays factual high-level project risk metrics and taxonomy distributions
 * directly from backend response without client-side recalculations.
 */

import type { ProjectRiskSummary } from '../types'

interface RiskSummaryCardsProps {
  summary?: ProjectRiskSummary
  isLoading?: boolean
}

export function RiskSummaryCards({ summary, isLoading }: RiskSummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="space-y-4" data-testid="risk-summary-loading">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, idx) => (
            <div
              key={idx}
              className="bg-white border border-gray-200 rounded-lg p-4 h-24 animate-pulse"
            >
              <div className="h-3 bg-gray-200 rounded w-2/3 mb-3" />
              <div className="h-6 bg-gray-200 rounded w-1/2" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6 text-center text-sm text-gray-500">
        No risk summary data available.
      </div>
    )
  }

  const kpis = [
    {
      label: 'Total Activities',
      value: summary.total_activities,
      accent: 'border-l-4 border-l-gray-400',
      valueColor: 'text-gray-900',
    },
    {
      label: 'Critical Risk',
      value: summary.critical_severity_count,
      accent: 'border-l-4 border-l-rose-500',
      valueColor: 'text-rose-700',
    },
    {
      label: 'High Risk',
      value: summary.high_severity_count,
      accent: 'border-l-4 border-l-amber-500',
      valueColor: 'text-amber-700',
    },
    {
      label: 'Medium Risk',
      value: summary.medium_severity_count,
      accent: 'border-l-4 border-l-yellow-500',
      valueColor: 'text-yellow-700',
    },
    {
      label: 'Low Risk',
      value: summary.low_severity_count,
      accent: 'border-l-4 border-l-emerald-500',
      valueColor: 'text-emerald-700',
    },
    {
      label: 'Average Risk Score',
      value: summary.average_risk_score !== null && summary.average_risk_score !== undefined
        ? `${summary.average_risk_score}`
        : '—',
      accent: 'border-l-4 border-l-blue-500',
      valueColor: 'text-blue-700',
    },
  ]

  const categories = [
    { label: 'Critical Path Delay', count: summary.critical_path_delay_count, color: 'bg-rose-50 text-rose-700 border-rose-200' },
    { label: 'Float Erosion', count: summary.float_erosion_count, color: 'bg-amber-50 text-amber-700 border-amber-200' },
    { label: 'Downstream Bottleneck', count: summary.downstream_bottleneck_count, color: 'bg-orange-50 text-orange-700 border-orange-200' },
    { label: 'Predecessor Blocker', count: summary.predecessor_blocker_count, color: 'bg-purple-50 text-purple-700 border-purple-200' },
    { label: 'Milestone Lag', count: summary.unquantified_milestone_lag_count, color: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
    { label: 'Unit Mismatch Exposure', count: summary.unit_mismatch_exposure_count, color: 'bg-slate-50 text-slate-700 border-slate-200' },
  ]

  return (
    <div className="space-y-4">
      {/* 1. Main KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className={`bg-white border border-gray-200 rounded-lg p-4 shadow-sm ${kpi.accent}`}
          >
            <span className="block text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {kpi.label}
            </span>
            <span className={`block text-2xl font-bold mt-1 tracking-tight ${kpi.valueColor}`}>
              {kpi.value}
            </span>
          </div>
        ))}
      </div>

      {/* 2. Taxonomy Distribution Pills */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <span className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
          Active Risk Categories
        </span>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <div
              key={cat.label}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${cat.color}`}
            >
              <span>{cat.label}:</span>
              <span className="font-bold">{cat.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
