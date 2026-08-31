/**
 * AuditFilterBar — Server-side filter controls for the protected audit trail.
 */

import { Button } from '@/components/ui/button'
import type { AuditEventType, AuditFilterParams } from '../types'

interface AuditFilterBarProps {
  filters: AuditFilterParams
  onFilterChange: (updated: Partial<AuditFilterParams>) => void
  onReset: () => void
}

const EVENT_TYPE_OPTIONS: { value: AuditEventType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Event Types' },
  { value: 'FIELD_INPUT_SUBMITTED', label: 'Field Input Submitted' },
  { value: 'AI_EXTRACTION_COMPLETED', label: 'AI Extraction Completed' },
  { value: 'AI_MATCH_GENERATED', label: 'AI Match Generated' },
  { value: 'PLANNER_DECISION_RECORDED', label: 'Planner Decision Recorded' },
  { value: 'APPROVED_ACTUAL_COMMITTED', label: 'Approved Actual Committed' },
  { value: 'DEPENDENCY_EDGE_MUTATED', label: 'Dependency Edge Mutated' },
]

export function AuditFilterBar({
  filters,
  onFilterChange,
  onReset,
}: AuditFilterBarProps) {
  const hasActiveFilters =
    (filters.event_type && filters.event_type !== 'all') ||
    Boolean(filters.entity_type?.trim()) ||
    Boolean(filters.start_date?.trim()) ||
    Boolean(filters.end_date?.trim())

  return (
    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm mb-6 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
      {/* Filters Group */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Event Type Filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="audit-event-type-filter" className="text-xs font-semibold text-gray-600">
            Event Type
          </label>
          <select
            id="audit-event-type-filter"
            value={filters.event_type || 'all'}
            onChange={(e) =>
              onFilterChange({
                event_type: e.target.value as AuditEventType | 'all',
              })
            }
            className="text-sm font-medium border border-gray-300 rounded-lg px-3 py-1.5 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition-colors"
          >
            {EVENT_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Entity Type Filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="audit-entity-type-filter" className="text-xs font-semibold text-gray-600">
            Entity Type
          </label>
          <input
            id="audit-entity-type-filter"
            type="text"
            placeholder="e.g. approved_actual"
            value={filters.entity_type || ''}
            onChange={(e) => onFilterChange({ entity_type: e.target.value })}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition-colors w-40"
          />
        </div>

        {/* Start Date */}
        <div className="flex flex-col gap-1">
          <label htmlFor="audit-start-date-filter" className="text-xs font-semibold text-gray-600">
            From Date
          </label>
          <input
            id="audit-start-date-filter"
            type="date"
            value={filters.start_date || ''}
            onChange={(e) => onFilterChange({ start_date: e.target.value })}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition-colors"
          />
        </div>

        {/* End Date */}
        <div className="flex flex-col gap-1">
          <label htmlFor="audit-end-date-filter" className="text-xs font-semibold text-gray-600">
            To Date
          </label>
          <input
            id="audit-end-date-filter"
            type="date"
            value={filters.end_date || ''}
            onChange={(e) => onFilterChange({ end_date: e.target.value })}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition-colors"
          />
        </div>
      </div>

      {/* Clear Filters Action */}
      {hasActiveFilters && (
        <div className="self-end md:self-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="text-xs text-gray-600 hover:text-gray-900"
          >
            Clear filters
          </Button>
        </div>
      )}
    </div>
  )
}
