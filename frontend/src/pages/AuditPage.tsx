import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProject } from '@/features/projects/useProject'
import { Button } from '@/components/ui/button'
import { getAuditEvents, formatAuditError } from '@/features/audit/api'
import { AuditFilterBar } from '@/features/audit/components/AuditFilterBar'
import { AuditPagination } from '@/features/audit/components/AuditPagination'
import { AuditEventTable } from '@/features/audit/components/AuditEventTable'
import { AuditEventCard } from '@/features/audit/components/AuditEventCard'
import { ProvenanceDrawer } from '@/features/audit/components/ProvenanceDrawer'
import type { AuditFilterParams } from '@/features/audit/types'

export default function AuditPage() {
  const { selectedProjectId } = useProject()

  const [filters, setFilters] = useState<AuditFilterParams>({
    limit: 50,
    offset: 0,
    event_type: 'all',
  })

  const [provenanceTarget, setProvenanceTarget] = useState<{
    entityType: string
    entityId: string
  } | null>(null)

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['audit-events', selectedProjectId, filters],
    queryFn: () => getAuditEvents(selectedProjectId!, filters),
    enabled: Boolean(selectedProjectId),
    staleTime: 30_000,
  })

  const handleFilterChange = (updated: Partial<AuditFilterParams>) => {
    setFilters((prev) => ({
      ...prev,
      ...updated,
      offset: 0, // Reset pagination to page 0 whenever filters change
    }))
  }

  const handleResetFilters = () => {
    setFilters({
      limit: 50,
      offset: 0,
      event_type: 'all',
    })
  }

  const handlePageChange = (newOffset: number) => {
    setFilters((prev) => ({
      ...prev,
      offset: newOffset,
    }))
  }

  if (!selectedProjectId) {
    return (
      <div className="p-8 text-center bg-white rounded-2xl border border-gray-200 shadow-sm max-w-md mx-auto my-12">
        <h2 className="text-lg font-bold text-gray-900 mb-2">No Project Selected</h2>
        <p className="text-sm text-gray-500">
          Please select a project from the top navigation bar to view its immutable audit trail.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Audit Trail</h1>
          <p className="text-sm text-gray-500 mt-1">
            Immutable lifecycle history and provenance
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <AuditFilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        onReset={handleResetFilters}
      />

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="bg-white rounded-xl border border-gray-200 p-8 shadow-sm" role="status">
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-8 h-8 border-3 border-amber-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-gray-500 font-medium">Loading audit events stream...</p>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {isError && (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 space-y-3 shadow-sm" role="alert">
          <h3 className="font-bold text-sm">Failed to load audit events</h3>
          <p className="text-xs">{formatAuditError(error)}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="text-xs">
            Retry
          </Button>
        </div>
      )}

      {/* Audit Stream Table & Mobile Cards */}
      {!isLoading && !isError && data && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
          {data.items.length === 0 ? (
            <div className="py-16 text-center text-gray-500 text-sm flex flex-col items-center gap-3">
              <p>No audit events match the selected filters.</p>
              <Button variant="ghost" size="sm" onClick={handleResetFilters} className="text-xs text-amber-600">
                Clear filters
              </Button>
            </div>
          ) : (
            <>
              {/* Desktop & Tablet Table */}
              <div className="hidden md:block">
                <AuditEventTable
                  events={data.items}
                  onViewProvenance={(type, id) =>
                    setProvenanceTarget({ entityType: type, entityId: id })
                  }
                />
              </div>

              {/* Mobile Cards */}
              <div className="md:hidden p-4 flex flex-col gap-3">
                {data.items.map((event) => (
                  <AuditEventCard
                    key={event.id}
                    event={event}
                    onViewProvenance={(type, id) =>
                      setProvenanceTarget({ entityType: type, entityId: id })
                    }
                  />
                ))}
              </div>

              {/* Pagination */}
              <AuditPagination
                total={data.total}
                limit={data.limit}
                offset={data.offset}
                onPageChange={handlePageChange}
              />
            </>
          )}
        </div>
      )}

      {/* Provenance Detail Drawer */}
      <ProvenanceDrawer
        projectId={selectedProjectId}
        entityType={provenanceTarget?.entityType || null}
        entityId={provenanceTarget?.entityId || null}
        onClose={() => setProvenanceTarget(null)}
      />
    </div>
  )
}
