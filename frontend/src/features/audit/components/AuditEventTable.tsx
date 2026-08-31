/**
 * AuditEventTable — Full tabular display of the chronological audit event stream.
 */

import { Button } from '@/components/ui/button'
import { AuditEventBadge } from './AuditEventBadge'
import type { AuditEvent } from '../types'

interface AuditEventTableProps {
  events: AuditEvent[]
  onViewProvenance: (entityType: string, entityId: string) => void
}

export function AuditEventTable({
  events,
  onViewProvenance,
}: AuditEventTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-left">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Timestamp
            </th>
            <th scope="col" className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Event Type
            </th>
            <th scope="col" className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Entity
            </th>
            <th scope="col" className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Actor
            </th>
            <th scope="col" className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider text-right">
              Lineage
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {events.map((event) => {
            const formattedDate = new Date(event.timestamp).toLocaleString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })

            const actorLabel = event.actor.is_system
              ? 'SiteSync System'
              : event.actor.actor_name || event.actor.actor_email || event.actor.role || 'User'

            return (
              <tr key={event.id} className="hover:bg-gray-50 transition-colors">
                {/* Timestamp */}
                <td className="px-4 py-3.5 whitespace-nowrap text-xs text-gray-600 font-mono">
                  {formattedDate}
                </td>

                {/* Event Type */}
                <td className="px-4 py-3.5 whitespace-nowrap">
                  <AuditEventBadge eventType={event.event_type} />
                </td>

                {/* Entity */}
                <td className="px-4 py-3.5 whitespace-nowrap">
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold text-gray-900 capitalize">
                      {event.entity_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[11px] text-gray-500 font-mono truncate max-w-[180px]">
                      {event.entity_id}
                    </span>
                  </div>
                </td>

                {/* Actor */}
                <td className="px-4 py-3.5 whitespace-nowrap">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        event.actor.is_system ? 'bg-indigo-500' : 'bg-emerald-500'
                      }`}
                      aria-hidden="true"
                    />
                    <span className="text-xs font-medium text-gray-800">{actorLabel}</span>
                  </div>
                </td>

                {/* Provenance Action */}
                <td className="px-4 py-3.5 whitespace-nowrap text-right text-xs">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onViewProvenance(event.entity_type, event.entity_id)}
                    className="text-xs text-amber-700 border-amber-200 bg-amber-50/50 hover:bg-amber-100/70"
                    aria-label={`View provenance for ${event.entity_type} ${event.entity_id}`}
                  >
                    View Provenance
                  </Button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
