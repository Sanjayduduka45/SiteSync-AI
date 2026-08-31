/**
 * ApprovedActualsTable — Displays official human-verified construction progress actuals.
 * Renders activities, verified quantities, work dates, approval statuses,
 * decider info, expandable evidence chips, and planner notes.
 */

import { useState } from 'react'
import type { ScheduleActivity } from '@/features/schedules/types'
import type { ApprovedActualResponse } from '../types'

interface ApprovedActualsTableProps {
  items: ApprovedActualResponse[]
  activitiesMap?: Record<string, ScheduleActivity>
  isLoading?: boolean
}

export function ApprovedActualsTable({
  items,
  activitiesMap = {},
  isLoading = false,
}: ApprovedActualsTableProps) {
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({})
  const [expandedNotes, setExpandedNotes] = useState<Record<string, boolean>>({})

  const toggleEvidence = (id: string) => {
    setExpandedEvidence((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const toggleNotes = (id: string) => {
    setExpandedNotes((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const formatDateTime = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return iso
    }
  }

  const parseEvidenceTokens = (sourceEvidence?: unknown[]): string[] => {
    if (!sourceEvidence || !Array.isArray(sourceEvidence)) return []
    const tokens: string[] = []
    for (const item of sourceEvidence) {
      if (typeof item === 'string') {
        tokens.push(item)
      } else if (item && typeof item === 'object' && 'token' in item) {
        tokens.push(String((item as { token: unknown }).token))
      }
    }
    return tokens
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-2xs">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-2" />
        <p className="text-xs text-gray-500 font-medium">Loading approved actuals…</p>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center shadow-2xs space-y-2">
        <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-700 mx-auto flex items-center justify-center text-xl font-bold border border-emerald-100">
          ✓
        </div>
        <h3 className="text-sm font-bold text-gray-900">No approved actuals yet.</h3>
        <p className="text-xs text-gray-500 max-w-md mx-auto">
          Approved progress will appear here after a Planner or Admin reviews an AI recommendation.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-2xs overflow-hidden">
      {/* Desktop & Tablet Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs" data-testid="approved-actuals-table">
          <thead className="bg-gray-50 text-gray-600 font-bold uppercase tracking-wider text-[10px]">
            <tr>
              <th scope="col" className="px-4 py-3">
                Activity
              </th>
              <th scope="col" className="px-4 py-3">
                Actual Progress
              </th>
              <th scope="col" className="px-4 py-3">
                Work Date
              </th>
              <th scope="col" className="px-4 py-3">
                Approval Status
              </th>
              <th scope="col" className="px-4 py-3">
                Approved By
              </th>
              <th scope="col" className="px-4 py-3">
                Approved At
              </th>
              <th scope="col" className="px-4 py-3">
                Evidence
              </th>
              <th scope="col" className="px-4 py-3">
                Notes
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {items.map((actual) => {
              const activity = activitiesMap[actual.schedule_activity_id]
              const activityCode = activity?.activity_code || 'ACT'
              const activityName = activity?.name || 'Schedule Activity'
              const discipline = activity?.discipline

              const evidenceTokens = parseEvidenceTokens(actual.source_evidence)
              const hasEvidence = evidenceTokens.length > 0
              const isEvidenceExpanded = expandedEvidence[actual.id] ?? false

              const hasNotes = Boolean(actual.notes && actual.notes.trim())
              const isNotesLong = (actual.notes?.length ?? 0) > 45
              const isNotesExpanded = expandedNotes[actual.id] ?? false

              return (
                <tr key={actual.id} className="hover:bg-gray-50/80 transition-colors" data-testid={`actual-row-${actual.id}`}>
                  {/* 1. Activity */}
                  <td className="px-4 py-3.5 align-top">
                    <div className="font-semibold text-gray-900 flex items-center gap-1.5 flex-wrap">
                      <span className="font-mono text-[11px] bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded border border-gray-200">
                        {activityCode}
                      </span>
                      <span>{activityName}</span>
                    </div>
                    {discipline && (
                      <span className="text-[10px] text-gray-400 font-medium block mt-0.5">
                        {discipline}
                      </span>
                    )}
                  </td>

                  {/* 2. Actual Progress */}
                  <td className="px-4 py-3.5 align-top whitespace-nowrap">
                    <span className="font-bold text-gray-900 text-sm">
                      {actual.actual_quantity !== null && actual.actual_quantity !== undefined
                        ? actual.actual_quantity
                        : '—'}
                    </span>{' '}
                    <span className="text-gray-600 font-medium">{actual.actual_unit || ''}</span>
                  </td>

                  {/* 3. Work Date */}
                  <td className="px-4 py-3.5 align-top whitespace-nowrap font-medium text-gray-800">
                    {actual.actual_date}
                  </td>

                  {/* 4. Approval Status */}
                  <td className="px-4 py-3.5 align-top whitespace-nowrap">
                    {actual.is_modified ? (
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200"
                        role="status"
                        aria-label="Approval status: Modified & Approved"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                        Modified & Approved
                      </span>
                    ) : (
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200"
                        role="status"
                        aria-label="Approval status: Approved"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                        Approved
                      </span>
                    )}
                  </td>

                  {/* 5. Approved By */}
                  <td className="px-4 py-3.5 align-top">
                    <span className="font-medium text-gray-900 block truncate max-w-[140px]" title={actual.approved_by}>
                      {actual.approved_by || 'Project Planner'}
                    </span>
                  </td>

                  {/* 6. Approved At */}
                  <td className="px-4 py-3.5 align-top whitespace-nowrap text-gray-500 text-[11px]">
                    {formatDateTime(actual.approved_at || actual.created_at)}
                  </td>

                  {/* 7. Evidence */}
                  <td className="px-4 py-3.5 align-top">
                    {hasEvidence ? (
                      <div className="space-y-1">
                        <button
                          type="button"
                          onClick={() => toggleEvidence(actual.id)}
                          className="text-[11px] font-semibold text-blue-700 hover:text-blue-900 cursor-pointer flex items-center gap-1"
                          aria-expanded={isEvidenceExpanded}
                        >
                          <span>Evidence ({evidenceTokens.length})</span>
                          <span>{isEvidenceExpanded ? '▲' : '▼'}</span>
                        </button>

                        {isEvidenceExpanded && (
                          <div className="flex flex-wrap gap-1 mt-1 max-w-xs" data-testid="evidence-chips">
                            {evidenceTokens.map((token, tIdx) => (
                              <span
                                key={tIdx}
                                className="inline-block text-[10px] bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded border border-gray-200 font-mono"
                              >
                                "{token}"
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-400 italic text-[11px]">No evidence tokens</span>
                    )}
                  </td>

                  {/* 8. Notes */}
                  <td className="px-4 py-3.5 align-top max-w-xs">
                    {hasNotes ? (
                      <div className="text-[11px] text-gray-700">
                        {isNotesLong && !isNotesExpanded ? (
                          <>
                            <span className="italic">{actual.notes?.slice(0, 45)}…</span>{' '}
                            <button
                              type="button"
                              onClick={() => toggleNotes(actual.id)}
                              className="text-blue-600 hover:text-blue-800 font-medium text-[10px] cursor-pointer inline ml-1"
                            >
                              More
                            </button>
                          </>
                        ) : (
                          <>
                            <span className="italic">"{actual.notes}"</span>
                            {isNotesLong && (
                              <button
                                type="button"
                                onClick={() => toggleNotes(actual.id)}
                                className="text-blue-600 hover:text-blue-800 font-medium text-[10px] cursor-pointer block mt-0.5"
                              >
                                Less
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-400 italic text-[11px]">—</span>
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
