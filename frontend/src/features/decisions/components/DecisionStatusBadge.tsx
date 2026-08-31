/**
 * DecisionStatusBadge — Visualizes the state of a human planner decision.
 * Displays semantic status badges, decider identity, timestamp, and rejection reasons.
 */

import type { PlannerDecisionResponse } from '../types'

interface DecisionStatusBadgeProps {
  decision: PlannerDecisionResponse
}

export function DecisionStatusBadge({ decision }: DecisionStatusBadgeProps) {
  const badgeConfig = {
    approved: {
      label: 'Approved',
      badgeClass: 'bg-emerald-50 text-emerald-800 border-emerald-300',
      dotClass: 'bg-emerald-600',
      icon: '✓',
    },
    modified: {
      label: 'Modified',
      badgeClass: 'bg-blue-50 text-blue-800 border-blue-300',
      dotClass: 'bg-blue-600',
      icon: '✎',
    },
    rejected: {
      label: 'Rejected',
      badgeClass: 'bg-rose-50 text-rose-800 border-rose-300',
      dotClass: 'bg-rose-600',
      icon: '✕',
    },
  }[decision.decision] ?? {
    label: decision.decision,
    badgeClass: 'bg-gray-50 text-gray-800 border-gray-300',
    dotClass: 'bg-gray-600',
    icon: '•',
  }

  const formatTimestamp = (iso: string) => {
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

  return (
    <div
      className="p-3 bg-gray-50/90 rounded-lg border border-gray-200 space-y-2 text-xs"
      data-testid="decision-status-container"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${badgeConfig.badgeClass}`}
          role="status"
          aria-label={`Decision status: ${badgeConfig.label}`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${badgeConfig.dotClass}`} />
          <span>{badgeConfig.label}</span>
        </span>

        <span className="text-[11px] text-gray-500 font-medium">
          {formatTimestamp(decision.decided_at || decision.created_at)}
        </span>
      </div>

      <div className="text-[11px] text-gray-600 space-y-1">
        <p>
          <span className="font-medium text-gray-700">Decided by:</span>{' '}
          <span className="font-mono text-gray-800">{decision.decided_by}</span>
        </p>

        {decision.decision === 'rejected' && decision.rejection_reason && (
          <div className="mt-2 p-2 bg-white rounded border border-rose-200 text-rose-900">
            <span className="font-bold text-rose-800 block text-[10px] uppercase tracking-wider">
              Rejection Reason
            </span>
            <p className="mt-0.5 italic">"{decision.rejection_reason}"</p>
          </div>
        )}

        {decision.decision === 'modified' && decision.modified_payload && (
          <div className="mt-2 p-2 bg-white rounded border border-blue-200 text-blue-950 space-y-0.5">
            <span className="font-bold text-blue-900 block text-[10px] uppercase tracking-wider">
              Modified Values
            </span>
            {decision.modified_payload.actual_quantity !== undefined &&
              decision.modified_payload.actual_quantity !== null && (
                <p>
                  <span className="text-gray-500">Progress:</span>{' '}
                  <span className="font-semibold">
                    {String(decision.modified_payload.actual_quantity)}{' '}
                    {decision.modified_payload.actual_unit
                      ? String(decision.modified_payload.actual_unit)
                      : ''}
                  </span>
                </p>
              )}
            {decision.modified_payload.actual_date ? (
              <p>
                <span className="text-gray-500">Date:</span>{' '}
                <span className="font-medium">
                  {String(decision.modified_payload.actual_date)}
                </span>
              </p>
            ) : null}
            {decision.modified_payload.notes ? (
              <p className="italic text-gray-600">
                "{String(decision.modified_payload.notes)}"
              </p>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
