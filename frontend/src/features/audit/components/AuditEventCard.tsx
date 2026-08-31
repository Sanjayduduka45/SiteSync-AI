/**
 * AuditEventCard — Mobile card presentation for an audit event.
 */

import { Button } from '@/components/ui/button'
import { AuditEventBadge } from './AuditEventBadge'
import type { AuditEvent } from '../types'

interface AuditEventCardProps {
  event: AuditEvent
  onViewProvenance: (entityType: string, entityId: string) => void
}

export function AuditEventCard({ event, onViewProvenance }: AuditEventCardProps) {
  const formattedDate = new Date(event.timestamp).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  const actorLabel = event.actor.is_system
    ? 'SiteSync System'
    : event.actor.actor_name || event.actor.actor_email || event.actor.role || 'User'

  return (
    <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <AuditEventBadge eventType={event.event_type} />
        <span className="text-[11px] text-gray-500 font-mono">{formattedDate}</span>
      </div>

      <div className="flex flex-col text-xs gap-1">
        <div className="flex items-center justify-between text-gray-600">
          <span className="font-medium">Entity:</span>
          <span className="font-semibold text-gray-900 capitalize">
            {event.entity_type.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="flex items-center justify-between text-gray-600">
          <span className="font-medium">Actor:</span>
          <span className="font-medium text-gray-800">{actorLabel}</span>
        </div>
      </div>

      <div className="pt-2 border-t border-gray-100 flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onViewProvenance(event.entity_type, event.entity_id)}
          className="text-xs text-amber-700 border-amber-200 bg-amber-50/50 hover:bg-amber-100/70 w-full"
        >
          View Provenance
        </Button>
      </div>
    </div>
  )
}
