import type { AuditEventType } from '../types'

interface AuditEventBadgeProps {
  eventType: AuditEventType
}

const EVENT_CONFIG: Record<
  AuditEventType,
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  FIELD_INPUT_SUBMITTED: {
    label: 'Field Input',
    bg: 'bg-sky-50',
    text: 'text-sky-700',
    border: 'border-sky-200',
    dot: 'bg-sky-500',
  },
  AI_EXTRACTION_COMPLETED: {
    label: 'AI Extraction',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
    dot: 'bg-indigo-500',
  },
  AI_MATCH_GENERATED: {
    label: 'Match Recommendation',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
    dot: 'bg-purple-500',
  },
  PLANNER_DECISION_RECORDED: {
    label: 'Planner Decision',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
    dot: 'bg-amber-500',
  },
  APPROVED_ACTUAL_COMMITTED: {
    label: 'Approved Actual',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
  },
  DEPENDENCY_EDGE_MUTATED: {
    label: 'Dependency Change',
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    dot: 'bg-slate-500',
  },
}

export function AuditEventBadge({ eventType }: AuditEventBadgeProps) {
  const config = EVENT_CONFIG[eventType] || {
    label: eventType,
    bg: 'bg-gray-50',
    text: 'text-gray-700',
    border: 'border-gray-200',
    dot: 'bg-gray-400',
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${config.bg} ${config.text} ${config.border}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  )
}
