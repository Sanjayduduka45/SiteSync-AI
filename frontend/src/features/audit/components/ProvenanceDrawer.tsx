/**
 * ProvenanceDrawer — Flyout panel presenting the causal provenance graph for an entity.
 */

import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { getProvenance, formatAuditError } from '../api'
import { ProvenanceTimeline } from './ProvenanceTimeline'

interface ProvenanceDrawerProps {
  projectId: string
  entityType: string | null
  entityId: string | null
  onClose: () => void
}

export function ProvenanceDrawer({
  projectId,
  entityType,
  entityId,
  onClose,
}: ProvenanceDrawerProps) {
  const isOpen = Boolean(entityType && entityId)

  const {
    data: chain,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['provenance', projectId, entityType, entityId],
    queryFn: () => getProvenance(projectId, entityType!, entityId!),
    enabled: isOpen && Boolean(projectId),
    staleTime: 60_000,
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="provenance-drawer-title">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md md:max-w-lg bg-white shadow-2xl flex flex-col">
          {/* Header */}
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/50">
            <div>
              <h3 id="provenance-drawer-title" className="text-base font-bold text-gray-900">
                Provenance Lineage
              </h3>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {entityType?.toUpperCase()} · {entityId}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-gray-500 hover:text-gray-900"
              aria-label="Close provenance panel"
            >
              ✕
            </Button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading && (
              <div className="flex flex-col items-center justify-center py-12 gap-3" role="status">
                <div className="w-8 h-8 border-3 border-amber-600 border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-gray-500 font-medium">Resolving causal provenance graph...</p>
              </div>
            )}

            {isError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs space-y-3" role="alert">
                <p className="font-semibold">Failed to resolve provenance</p>
                <p>{formatAuditError(error)}</p>
                <Button variant="outline" size="sm" onClick={() => refetch()} className="text-xs">
                  Retry
                </Button>
              </div>
            )}

            {!isLoading && !isError && chain && (
              <ProvenanceTimeline chain={chain} />
            )}

            {!isLoading && !isError && (!chain || chain.nodes.length === 0) && (
              <div className="text-center py-12 text-gray-500 text-xs">
                No provenance records are available for this entity.
              </div>
            )}
          </div>

          {/* Footer */}
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
