/**
 * SchedulePage — Primary Baseline Schedule view for SiteSync AI Phase 6.7.
 * Provides construction schedule activity visibility and planner creation capabilities.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useProject } from '@/features/projects/useProject'
import { getScheduleActivities, createScheduleActivity } from '@/features/schedules/api'
import { ScheduleActivityTable } from '@/features/schedules/components/ScheduleActivityTable'
import { CreateScheduleActivityModal } from '@/features/schedules/components/CreateScheduleActivityModal'
import type { ScheduleActivityCreateInput } from '@/features/schedules/types'

export default function SchedulePage() {
  const { selectedProjectId, currentRole } = useProject()
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const canManage = currentRole === 'planner' || currentRole === 'admin'

  const {
    data: response,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['schedule-activities', selectedProjectId],
    queryFn: () => {
      if (!selectedProjectId) throw new Error('No project selected')
      return getScheduleActivities(selectedProjectId)
    },
    enabled: !!selectedProjectId,
  })

  const createMutation = useMutation({
    mutationFn: (input: ScheduleActivityCreateInput) => {
      if (!selectedProjectId) throw new Error('No project selected')
      return createScheduleActivity(selectedProjectId, input)
    },
    onSuccess: () => {
      setActionError(null)
      queryClient.invalidateQueries({ queryKey: ['schedule-activities', selectedProjectId] })
    },
    onError: (err: unknown) => {
      setActionError(err instanceof Error ? err.message : 'Failed to create schedule activity')
    },
  })

  const activities = response?.items || []

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <span>📅</span> Project Baseline Schedule
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Master construction schedule activities for AI progress matching and alignment.
          </p>
        </div>

        {canManage && (
          <Button
            size="sm"
            onClick={() => setIsModalOpen(true)}
            className="bg-gray-900 text-white hover:bg-gray-800 text-xs self-start sm:self-auto"
          >
            + Add Schedule Activity
          </Button>
        )}
      </div>

      {/* Error Banner */}
      {(isError || actionError) && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center justify-between">
          <span>{actionError || (error instanceof Error ? error.message : 'Failed to load schedule')}</span>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="text-xs ml-4">
            Retry
          </Button>
        </div>
      )}

      {/* Activities Grid / Table */}
      <ScheduleActivityTable activities={activities} isLoading={isLoading} />

      {/* Creation Modal */}
      <CreateScheduleActivityModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={async (data) => {
          await createMutation.mutateAsync(data)
        }}
        isSubmitting={createMutation.isPending}
      />
    </div>
  )
}
