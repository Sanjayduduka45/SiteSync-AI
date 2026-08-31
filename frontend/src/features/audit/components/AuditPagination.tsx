/**
 * AuditPagination — Deterministic server-side pagination controls for audit events.
 */

import { Button } from '@/components/ui/button'

interface AuditPaginationProps {
  total: number
  limit: number
  offset: number
  onPageChange: (newOffset: number) => void
}

export function AuditPagination({
  total,
  limit,
  offset,
  onPageChange,
}: AuditPaginationProps) {
  if (total <= 0) return null

  const start = offset + 1
  const end = Math.min(offset + limit, total)
  const hasPrev = offset > 0
  const hasNext = offset + limit < total

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 sm:px-6 rounded-b-xl">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-700 font-medium">
          Showing <span className="font-semibold text-gray-900">{start}</span> to{' '}
          <span className="font-semibold text-gray-900">{end}</span> of{' '}
          <span className="font-semibold text-gray-900">{total}</span> events
        </span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!hasPrev}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          className="text-xs"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!hasNext}
          onClick={() => onPageChange(offset + limit)}
          className="text-xs"
        >
          Next
        </Button>
      </div>
    </div>
  )
}
