/**
 * Risk Register Filter Bar — SiteSync AI Phase 9.6.
 * Provides controls for filtering activities by Severity, Risk Category, WBS, and Discipline.
 * Automatically resets pagination offset to 0 upon filter modification.
 */

import { Button } from '@/components/ui/button'
import type { RiskCategory, RiskSeverityLevel } from '../types'

interface RiskFilterBarProps {
  severity: RiskSeverityLevel | 'all'
  category: RiskCategory | 'all'
  wbsCode: string
  discipline: string
  onSeverityChange: (sev: RiskSeverityLevel | 'all') => void
  onCategoryChange: (cat: RiskCategory | 'all') => void
  onWbsCodeChange: (wbs: string) => void
  onDisciplineChange: (disc: string) => void
  onClearFilters: () => void
}

export function RiskFilterBar({
  severity,
  category,
  wbsCode,
  discipline,
  onSeverityChange,
  onCategoryChange,
  onWbsCodeChange,
  onDisciplineChange,
  onClearFilters,
}: RiskFilterBarProps) {
  const hasActiveFilters =
    severity !== 'all' || category !== 'all' || Boolean(wbsCode.trim()) || Boolean(discipline.trim())

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Filter Risk Register
        </h3>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearFilters}
            className="text-xs text-gray-500 hover:text-gray-900 self-start sm:self-auto h-7 px-2"
          >
            Clear Filters
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Severity Filter */}
        <div>
          <label htmlFor="filter-severity" className="block text-xs font-medium text-gray-600 mb-1">
            Severity Level
          </label>
          <select
            id="filter-severity"
            value={severity}
            onChange={(e) => onSeverityChange(e.target.value as RiskSeverityLevel | 'all')}
            className="w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Category Filter */}
        <div>
          <label htmlFor="filter-category" className="block text-xs font-medium text-gray-600 mb-1">
            Risk Category
          </label>
          <select
            id="filter-category"
            value={category}
            onChange={(e) => onCategoryChange(e.target.value as RiskCategory | 'all')}
            className="w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
          >
            <option value="all">All Categories</option>
            <option value="critical_path_delay">Critical Path Delay</option>
            <option value="float_erosion">Float Erosion</option>
            <option value="downstream_bottleneck">Downstream Bottleneck</option>
            <option value="predecessor_blocker">Predecessor Blocker</option>
            <option value="unquantified_milestone_lag">Milestone Lag</option>
            <option value="unit_mismatch_exposure">Unit Mismatch Exposure</option>
          </select>
        </div>

        {/* WBS Filter */}
        <div>
          <label htmlFor="filter-risk-wbs" className="block text-xs font-medium text-gray-600 mb-1">
            WBS Code
          </label>
          <input
            id="filter-risk-wbs"
            type="text"
            placeholder="e.g. 1.1"
            value={wbsCode}
            onChange={(e) => onWbsCodeChange(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
        </div>

        {/* Discipline Filter */}
        <div>
          <label htmlFor="filter-risk-discipline" className="block text-xs font-medium text-gray-600 mb-1">
            Discipline
          </label>
          <input
            id="filter-risk-discipline"
            type="text"
            placeholder="e.g. Civil, Piping"
            value={discipline}
            onChange={(e) => onDisciplineChange(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-md px-3 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500"
          />
        </div>
      </div>
    </div>
  )
}
