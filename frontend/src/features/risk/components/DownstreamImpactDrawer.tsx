/**
 * Downstream Impact Drawer — SiteSync AI Phase 9.6 (ADR-016).
 * Slide-over panel displaying the full transitive downstream delay impact,
 * float erosion, and buffer absorption for a selected source activity.
 */

import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { formatRiskError, getDownstreamImpact } from '../api'
import type { DownstreamImpactSeverity } from '../types'

interface DownstreamImpactDrawerProps {
  projectId: string
  activityId: string | null
  isOpen: boolean
  onClose: () => void
}

const SEVERITY_PILLS: Record<DownstreamImpactSeverity, { label: string; style: string }> = {
  critical_slippage: { label: 'Critical Slippage', style: 'bg-rose-100 text-rose-800 border-rose-300' },
  buffer_absorbed: { label: 'Buffer Absorbed', style: 'bg-amber-100 text-amber-800 border-amber-300' },
  historical_completed: { label: 'Historical (Completed)', style: 'bg-gray-100 text-gray-700 border-gray-300' },
  unaffected: { label: 'Unaffected', style: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
}

export function DownstreamImpactDrawer({
  projectId,
  activityId,
  isOpen,
  onClose,
}: DownstreamImpactDrawerProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['downstream-impact', projectId, activityId],
    queryFn: () => getDownstreamImpact(projectId, activityId!),
    enabled: Boolean(projectId && activityId && isOpen),
  })

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-label="Downstream Impact Analysis">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-white shadow-2xl flex flex-col border-l border-gray-200">
          {/* Drawer Header */}
          <div className="p-6 border-b border-gray-200 flex items-start justify-between bg-gray-50/50">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-4 w-1.5 bg-blue-600 rounded-xs" />
                <h2 className="text-lg font-bold text-gray-900 tracking-tight">
                  Downstream Impact Analysis
                </h2>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Factual transitive schedule delay propagation and float erosion (ADR-016).
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-700 h-8 w-8 p-0 rounded-full"
              aria-label="Close drawer"
            >
              ✕
            </Button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {isLoading && (
              <div className="space-y-4" data-testid="downstream-drawer-loading">
                <div className="h-20 bg-gray-100 rounded animate-pulse" />
                <div className="h-40 bg-gray-100 rounded animate-pulse" />
              </div>
            )}

            {error && (
              <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-lg text-sm">
                <strong>Error: </strong> {formatRiskError(error)}
              </div>
            )}

            {data && (
              <div className="space-y-6">
                {/* 1. Source Summary Banner */}
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div>
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                        Source Activity
                      </span>
                      <h3 className="text-sm font-bold text-gray-900">
                        {`${data.source_activity_code} — ${data.source_name}`}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded border ${
                          data.source_delay_days > 0
                            ? 'bg-rose-100 text-rose-800 border-rose-300'
                            : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                        }`}
                      >
                        Delay: {data.source_delay_days > 0 ? `+${data.source_delay_days}d` : `${data.source_delay_days}d`}
                      </span>
                      {data.is_source_critical && (
                        <span className="text-xs font-bold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                          Critical Path
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Impact Summary Counters */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-200 text-center">
                    <div className="bg-white p-2 rounded border border-slate-200">
                      <span className="block text-[10px] text-gray-500 font-medium">Reachable Successors</span>
                      <strong className="text-base text-gray-900">{data.total_downstream_activities_count}</strong>
                    </div>
                    <div className="bg-white p-2 rounded border border-rose-200">
                      <span className="block text-[10px] text-rose-600 font-medium">Critical Slippage</span>
                      <strong className="text-base text-rose-700">{data.critical_slippage_count}</strong>
                    </div>
                    <div className="bg-white p-2 rounded border border-amber-200">
                      <span className="block text-[10px] text-amber-600 font-medium">Buffer Absorbed</span>
                      <strong className="text-base text-amber-700">{data.buffer_absorbed_count}</strong>
                    </div>
                    <div className="bg-white p-2 rounded border border-gray-200">
                      <span className="block text-[10px] text-gray-500 font-medium">Historical Completed</span>
                      <strong className="text-base text-gray-700">{data.historical_completed_count}</strong>
                    </div>
                  </div>
                </div>

                {/* 2. Transitive Successor Impact Tree */}
                <div>
                  <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider mb-3">
                    Transitive Successor Impact Graph ({data.impacted_successors.length})
                  </h4>

                  {data.impacted_successors.length === 0 ? (
                    <p className="text-xs text-gray-500 italic p-4 bg-gray-50 rounded border border-gray-200 text-center">
                      No downstream successors are connected to this activity.
                    </p>
                  ) : (
                    <div className="space-y-2.5">
                      {data.impacted_successors.map((succ) => {
                        const sev = SEVERITY_PILLS[succ.impact_severity] || SEVERITY_PILLS.unaffected

                        return (
                          <div
                            key={succ.activity_id}
                            className={`p-3.5 rounded-lg border text-xs transition-colors ${
                              succ.impact_severity === 'critical_slippage'
                                ? 'bg-rose-50/40 border-rose-200'
                                : succ.impact_severity === 'buffer_absorbed'
                                ? 'bg-amber-50/40 border-amber-200'
                                : 'bg-white border-gray-200'
                            }`}
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 mb-2">
                              <div>
                                <span className="font-mono font-bold text-gray-900 mr-2">
                                  {succ.activity_code}
                                </span>
                                <span className="font-medium text-gray-800">{succ.name}</span>
                              </div>
                              <div className="flex items-center gap-1.5 self-start sm:self-auto">
                                <span
                                  role="status"
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold border ${sev.style}`}
                                >
                                  {sev.label}
                                </span>
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
                                  Hop {succ.depth}
                                </span>
                              </div>
                            </div>

                            {/* Path and predecessor details */}
                            <div className="text-[11px] text-gray-600 font-mono bg-gray-50 p-2 rounded border border-gray-100 space-y-1 mb-2">
                              <div>
                                <span className="text-gray-400">Path: </span>
                                <span className="text-gray-800">{succ.path.join(' → ')}</span>
                              </div>
                              {succ.relationship_with_immediate_predecessor && (
                                <div className="text-[10px] text-gray-500">
                                  Link: {succ.relationship_with_immediate_predecessor}
                                  {succ.lag_days_with_immediate_predecessor !== 0 &&
                                    ` (Lag: ${succ.lag_days_with_immediate_predecessor}d)`}
                                </div>
                              )}
                            </div>

                            {/* Float & Delay Metrics */}
                            <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
                              <div className="bg-white/80 p-1.5 rounded border border-gray-100">
                                <span className="text-[10px] text-gray-400 block">Available Float</span>
                                <strong className="text-gray-700">
                                  {succ.total_float !== null ? `${succ.total_float}d` : '—'}
                                </strong>
                              </div>
                              <div className="bg-white/80 p-1.5 rounded border border-gray-100">
                                <span className="text-[10px] text-gray-400 block">Float Consumed</span>
                                <strong className="text-amber-700">{succ.float_consumed}d</strong>
                              </div>
                              <div className="bg-white/80 p-1.5 rounded border border-gray-100">
                                <span className="text-[10px] text-gray-400 block">Projected Delay</span>
                                <strong className={succ.projected_delay_days > 0 ? 'text-rose-700' : 'text-gray-700'}>
                                  {succ.projected_delay_days > 0 ? `+${succ.projected_delay_days}d` : `${succ.projected_delay_days}d`}
                                </strong>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Drawer Footer */}
          <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end">
            <Button variant="outline" size="sm" onClick={onClose} className="text-xs">
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
