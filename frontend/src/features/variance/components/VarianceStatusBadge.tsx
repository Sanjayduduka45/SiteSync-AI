/**
 * VarianceStatusBadge — Visual status indicator for Plan vs Actual alignment.
 * Strictly presents factual deterministic categories.
 */


import type { ActivityVarianceStatus } from '../types'

interface VarianceStatusBadgeProps {
  status: ActivityVarianceStatus
  className?: string
}

interface StatusConfig {
  label: string
  bgClass: string
  textClass: string
  borderClass: string
}

const STATUS_CONFIGS: Record<ActivityVarianceStatus, StatusConfig> = {
  not_started: {
    label: 'Not Started',
    bgClass: 'bg-gray-100',
    textClass: 'text-gray-700',
    borderClass: 'border-gray-300',
  },
  in_progress: {
    label: 'In Progress',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-700',
    borderClass: 'border-blue-200',
  },
  completed: {
    label: 'Completed',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-700',
    borderClass: 'border-emerald-200',
  },
  over_delivered: {
    label: 'Over Delivered',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-200',
  },
  unquantified: {
    label: 'Unquantified',
    bgClass: 'bg-purple-50',
    textClass: 'text-purple-700',
    borderClass: 'border-purple-200',
  },
  unit_mismatch: {
    label: 'Unit Mismatch',
    bgClass: 'bg-rose-50',
    textClass: 'text-rose-700',
    borderClass: 'border-rose-200',
  },
}

export function VarianceStatusBadge({ status, className = '' }: VarianceStatusBadgeProps) {
  const config = STATUS_CONFIGS[status] || STATUS_CONFIGS.not_started

  return (
    <span
      role="status"
      aria-label={`Activity Status: ${config.label}`}
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${config.bgClass} ${config.textClass} ${config.borderClass} ${className}`}
    >
      {config.label}
    </span>
  )
}
