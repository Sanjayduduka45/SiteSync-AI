/**
 * EventsPage — Field Events management for SiteSync AI (Phase 3).
 *
 * Capabilities:
 *  - Project-scoped field events listing
 *  - Create field event interaction
 *  - Search, discipline filtering, and status filtering
 *  - Event detail drawer showing structured metadata and future AI pipeline placeholders
 *  - Permission-aware action states (Admin / Planner / Supervisor vs Viewer)
 */

import { useState, type FormEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useProject } from '@/features/projects/useProject'
import { fetchEvents, createEvent } from '@/features/events/api'
import { fetchReports } from '@/features/reports/api'
import type { FieldEvent, FieldEventStatus } from '@/features/events/types'

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export default function EventsPage() {
  const { selectedProjectId, selectedProject, currentRole } = useProject()
  const queryClient = useQueryClient()

  const [searchQuery, setSearchQuery] = useState('')
  const [disciplineFilter, setDisciplineFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<FieldEvent | null>(null)

  // Create Form State
  const [description, setDescription] = useState('')
  const [eventType, setEventType] = useState('')
  const [discipline, setDiscipline] = useState('Piping')
  const [location, setLocation] = useState('')
  const [eventDate, setEventDate] = useState(() => new Date().toISOString().split('T')[0])
  const [progressPercent, setProgressPercent] = useState<number>(100)
  const [reportId, setReportId] = useState<string>('')
  const [formError, setFormError] = useState<string | null>(null)

  const isViewer = currentRole === 'viewer'

  // Fetch events query
  const {
    data: eventsData,
    isLoading: isLoadingEvents,
    isError: isEventsError,
    error: eventsError,
  } = useQuery({
    queryKey: ['events', selectedProjectId],
    queryFn: () => fetchEvents(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  // Fetch reports for dropdown in creation modal
  const { data: reportsData } = useQuery({
    queryKey: ['reports', selectedProjectId],
    queryFn: () => fetchReports(selectedProjectId!),
    enabled: Boolean(selectedProjectId && isCreateModalOpen),
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (payload: {
      report_id?: string | null
      event_type: string
      description: string
      discipline: string
      location: string
      event_date: string
      progress_percent: number
    }) => createEvent(selectedProjectId!, payload),
    onSuccess: (newEvent) => {
      queryClient.invalidateQueries({ queryKey: ['events', selectedProjectId] })
      setIsCreateModalOpen(false)
      setDescription('')
      setEventType('')
      setLocation('')
      setFormError(null)
      setSelectedEvent(newEvent)
    },
    onError: (err: unknown) => {
      setFormError(err instanceof Error ? err.message : 'Creation failed')
    },
  })

  const handleCreateSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError(null)

    if (!description.trim()) {
      setFormError('Event description is required.')
      return
    }
    if (!eventType.trim()) {
      setFormError('Event type is required.')
      return
    }
    if (!location.trim()) {
      setFormError('Location is required.')
      return
    }
    if (!eventDate) {
      setFormError('Event date is required.')
      return
    }
    if (progressPercent < 0 || progressPercent > 100) {
      setFormError('Progress percentage must be between 0 and 100.')
      return
    }

    createMutation.mutate({
      report_id: reportId ? reportId : null,
      event_type: eventType.trim(),
      description: description.trim(),
      discipline: discipline.trim(),
      location: location.trim(),
      event_date: eventDate,
      progress_percent: Number(progressPercent),
    })
  }

  // Filtered events
  const events = eventsData?.events ?? []
  const filteredEvents = events.filter((evt) => {
    const matchesSearch =
      evt.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      evt.location.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesDiscipline =
      disciplineFilter === 'all' || evt.discipline.toLowerCase() === disciplineFilter.toLowerCase()

    const matchesStatus = statusFilter === 'all' || evt.status.toLowerCase() === statusFilter.toLowerCase()

    return matchesSearch && matchesDiscipline && matchesStatus
  })

  const statusStyles: Record<FieldEventStatus, string> = {
    pending: 'bg-amber-50 text-amber-700 border-amber-200',
    processed: 'bg-blue-50 text-blue-700 border-blue-200',
    matched: 'bg-purple-50 text-purple-700 border-purple-200',
    needs_review: 'bg-orange-50 text-orange-700 border-orange-200',
    approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rejected: 'bg-red-50 text-red-700 border-red-200',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Field Events</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Structured events captured from construction field information for{' '}
            <span className="font-semibold text-gray-700">{selectedProject?.projectName ?? 'Project'}</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => setIsCreateModalOpen(true)}
            disabled={isViewer || !selectedProjectId}
            className="bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-40"
          >
            Create Event
          </Button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="w-full sm:w-80">
          <input
            type="text"
            placeholder="Search description, type, location…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-gray-500 uppercase">Discipline:</span>
            <select
              value={disciplineFilter}
              onChange={(e) => setDisciplineFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="all">All</option>
              <option value="piping">Piping</option>
              <option value="civil">Civil</option>
              <option value="electrical">Electrical</option>
              <option value="mechanical">Mechanical</option>
              <option value="structural">Structural</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-gray-500 uppercase">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="processed">Processed</option>
              <option value="needs_review">Needs Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>
      </div>

      {/* Events Table / Content Area */}
      {isLoadingEvents ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-3" />
          <p className="text-sm text-gray-500 font-medium">Loading field events…</p>
        </div>
      ) : isEventsError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            {eventsError instanceof Error ? eventsError.message : 'Failed to load events.'}
          </p>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="h-10 w-10 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3 text-gray-400 font-bold">
            ⚡
          </div>
          <h3 className="text-base font-semibold text-gray-900">No field events have been recorded yet.</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            {searchQuery || disciplineFilter !== 'all' || statusFilter !== 'all'
              ? 'No field events matched your filter criteria.'
              : 'Create physical field events from site logs or inspection reports.'}
          </p>
          {!isViewer && !searchQuery && disciplineFilter === 'all' && statusFilter === 'all' && (
            <Button
              onClick={() => setIsCreateModalOpen(true)}
              className="mt-4 bg-gray-900 text-white hover:bg-gray-800"
              size="sm"
            >
              Create First Event
            </Button>
          )}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-700">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3">Event Description</th>
                  <th className="px-4 py-3">Source Report</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Discipline</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredEvents.map((evt) => (
                  <tr
                    key={evt.id}
                    data-testid={`event-row-${evt.id}`}
                    onClick={() => setSelectedEvent(evt)}
                    className="hover:bg-amber-50/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3.5 font-medium text-gray-900">
                      <div className="font-semibold text-gray-900">{evt.event_type}</div>
                      <div className="text-xs text-gray-500 line-clamp-1">{evt.description}</div>
                    </td>
                    <td className="px-4 py-3.5 text-gray-600 text-xs">
                      {evt.report_name ? (
                        <span className="font-medium text-gray-800 bg-gray-100 px-2 py-0.5 rounded text-[11px]">
                          {evt.report_name}
                        </span>
                      ) : (
                        <span className="text-gray-400 italic">Direct Entry</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-gray-500 text-xs">{formatDate(evt.event_date)}</td>
                    <td className="px-4 py-3.5">
                      <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-xs font-medium">
                        {evt.discipline}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-gray-600 text-xs">{evt.location}</td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-gray-900 text-xs">{evt.progress_percent}%</span>
                        <div className="w-12 bg-gray-200 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-amber-600 h-full rounded-full"
                            style={{ width: `${Math.min(evt.progress_percent, 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border font-medium uppercase text-[10px] ${
                          statusStyles[evt.status] || 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {evt.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        type="button"
                        data-testid={`event-details-btn-${evt.id}`}
                        onClick={() => setSelectedEvent(evt)}
                        className="text-xs font-semibold text-amber-700 hover:text-amber-900 cursor-pointer"
                      >
                        View Details →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create Event Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6 shadow-xl border border-gray-200 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Create Field Event</h2>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {formError && (
              <div role="alert" className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Event Type <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Spool Erection, Concrete Pour, Cable Pulling"
                  value={eventType}
                  onChange={(e) => setEventType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Description of Work <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. Spool erection completed on Line 24 in Unit-1 Rack"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Discipline</label>
                  <select
                    value={discipline}
                    onChange={(e) => setDiscipline(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                  >
                    <option value="Piping">Piping</option>
                    <option value="Civil">Civil</option>
                    <option value="Electrical">Electrical</option>
                    <option value="Mechanical">Mechanical</option>
                    <option value="Structural">Structural</option>
                    <option value="Instrumentation">Instrumentation</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Location / Area <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Unit-1 / Piping Rack 3"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Event Date <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={eventDate}
                    onChange={(e) => setEventDate(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Progress (%)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={progressPercent}
                    onChange={(e) => setProgressPercent(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Linked Source Report (Optional)</label>
                <select
                  value={reportId}
                  onChange={(e) => setReportId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                >
                  <option value="">Direct Entry (No source report)</option>
                  {(reportsData?.reports ?? []).map((rep) => (
                    <option key={rep.id} value={rep.id}>
                      {rep.name} ({rep.file_name})
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsCreateModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending}
                  size="sm"
                  className="bg-gray-900 text-white hover:bg-gray-800"
                >
                  {createMutation.isPending ? 'Saving…' : 'Record Event'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Event Detail Drawer */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-xs">
          <div className="bg-white w-full max-w-md h-full shadow-2xl border-l border-gray-200 flex flex-col overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-gray-200 flex items-start justify-between bg-gray-50">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  Field Event
                </span>
                <h2 className="text-lg font-bold text-gray-900 mt-2">{selectedEvent.event_type}</h2>
                <p className="text-xs text-gray-500 mt-0.5">{selectedEvent.location}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEvent(null)}
                className="text-gray-400 hover:text-gray-600 font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Event Metadata Body */}
            <div className="p-6 space-y-6 flex-1">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Description</h3>
                <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded border border-gray-100">
                  {selectedEvent.description}
                </p>
              </div>

              <div className="space-y-3 bg-gray-50 p-4 rounded-lg border border-gray-100 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Discipline:</span>
                  <span className="font-semibold text-gray-900">{selectedEvent.discipline}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Location:</span>
                  <span className="font-semibold text-gray-900">{selectedEvent.location}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Event Date:</span>
                  <span className="font-semibold text-gray-900">{formatDate(selectedEvent.event_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Progress:</span>
                  <span className="font-bold text-amber-700">{selectedEvent.progress_percent}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Source Report:</span>
                  <span className="font-semibold text-gray-900">
                    {selectedEvent.report_name || 'Direct Field Entry'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Status:</span>
                  <span
                    className={`font-semibold uppercase text-[10px] px-1.5 py-0.5 rounded border ${
                      statusStyles[selectedEvent.status] || 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {selectedEvent.status}
                  </span>
                </div>
              </div>

              {/* Locked AI Placeholders for Future Phases */}
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700">Schedule Intelligence</h4>
                  <span className="text-[10px] font-semibold text-gray-400 bg-gray-200/60 px-1.5 py-0.5 rounded">
                    Future Phase
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">AI Schedule Match:</span>
                    <span className="font-medium text-gray-600">Not processed</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Confidence Score:</span>
                    <span className="font-medium text-gray-600">—</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Planner Decision:</span>
                    <span className="font-medium text-gray-600">Pending</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-gray-200 bg-gray-50 flex items-center justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedEvent(null)}
                className="text-xs"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
