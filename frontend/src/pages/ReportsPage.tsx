/**
 * ReportsPage — Field Reports management for SiteSync AI (Phase 3).
 *
 * Capabilities:
 *  - Project-scoped report listing
 *  - Upload report interaction (PDF, XLSX, CSV, TXT)
 *  - Search & status filtering
 *  - Report detail drawer showing metadata & linked field events
 *  - Permission-aware action states (Admin / Planner / Supervisor vs Viewer)
 */

import { useState, type FormEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useProject } from '@/features/projects/useProject'
import { fetchReports, createReport, deleteReport } from '@/features/reports/api'
import { fetchEvents } from '@/features/events/api'
import type { Report, ReportStatus } from '@/features/reports/types'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

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

export default function ReportsPage() {
  const { selectedProjectId, selectedProject, currentRole } = useProject()
  const queryClient = useQueryClient()

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)

  // Upload Form State
  const [reportName, setReportName] = useState('')
  const [fileName, setFileName] = useState('')
  const [fileType, setFileType] = useState('pdf')
  const [fileSize, setFileSize] = useState(1_500_000)
  const [source, setSource] = useState('manual_upload')
  const [uploadError, setUploadError] = useState<string | null>(null)

  const isViewer = currentRole === 'viewer'

  // Fetch reports query
  const {
    data: reportsData,
    isLoading: isLoadingReports,
    isError: isReportsError,
    error: reportsError,
  } = useQuery({
    queryKey: ['reports', selectedProjectId],
    queryFn: () => fetchReports(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  // Fetch linked events for selected report in detail drawer
  const { data: linkedEventsData, isLoading: isLoadingLinkedEvents } = useQuery({
    queryKey: ['events', selectedProjectId, selectedReport?.id],
    queryFn: () => fetchEvents(selectedProjectId!, selectedReport!.id),
    enabled: Boolean(selectedProjectId && selectedReport?.id),
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (payload: { name: string; file_name: string; file_type: string; file_size: number; source: string }) =>
      createReport(selectedProjectId!, payload),
    onSuccess: (newReport) => {
      queryClient.invalidateQueries({ queryKey: ['reports', selectedProjectId] })
      setIsUploadModalOpen(false)
      setReportName('')
      setFileName('')
      setUploadError(null)
      setSelectedReport(newReport)
    },
    onError: (err: unknown) => {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    },
  })

  // Delete mutation (Admin only)
  const deleteMutation = useMutation({
    mutationFn: (reportId: string) => deleteReport(selectedProjectId!, reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports', selectedProjectId] })
      if (selectedReport) {
        setSelectedReport(null)
      }
    },
  })

  const handleUploadSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setUploadError(null)

    if (!reportName.trim()) {
      setUploadError('Report name is required.')
      return
    }
    if (!fileName.trim()) {
      setUploadError('Please select or specify a filename.')
      return
    }

    uploadMutation.mutate({
      name: reportName.trim(),
      file_name: fileName.trim(),
      file_type: fileType,
      file_size: fileSize,
      source: source.trim() || 'manual_upload',
    })
  }

  // Filtered reports
  const reports = reportsData?.reports ?? []
  const filteredReports = reports.filter((r) => {
    const matchesSearch =
      r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.uploaded_by_email && r.uploaded_by_email.toLowerCase().includes(searchQuery.toLowerCase()))

    const matchesStatus = statusFilter === 'all' || r.status.toLowerCase() === statusFilter.toLowerCase()
    return matchesSearch && matchesStatus
  })

  const statusStyles: Record<ReportStatus, string> = {
    uploaded: 'bg-amber-50 text-amber-700 border-amber-200',
    processing: 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse',
    processed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    failed: 'bg-red-50 text-red-700 border-red-200',
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Field Reports</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Upload and manage project field information for{' '}
            <span className="font-semibold text-gray-700">{selectedProject?.projectName ?? 'Project'}</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => setIsUploadModalOpen(true)}
            disabled={isViewer || !selectedProjectId}
            className="bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-40"
          >
            Upload Report
          </Button>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="w-full sm:w-80">
          <input
            type="text"
            placeholder="Search by name, file or author…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs font-semibold text-gray-500 uppercase">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-2.5 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
          >
            <option value="all">All Statuses</option>
            <option value="uploaded">Uploaded</option>
            <option value="processing">Processing</option>
            <option value="processed">Processed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Reports Table / Content Area */}
      {isLoadingReports ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-3" />
          <p className="text-sm text-gray-500 font-medium">Loading field reports…</p>
        </div>
      ) : isReportsError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            {reportsError instanceof Error ? reportsError.message : 'Failed to load reports.'}
          </p>
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="h-10 w-10 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3 text-gray-400 font-bold">
            📄
          </div>
          <h3 className="text-base font-semibold text-gray-900">No field reports yet.</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            {searchQuery || statusFilter !== 'all'
              ? 'No reports matched your filters.'
              : 'Upload construction daily logs, inspection PDFs, or Excel diaries to begin capturing progress.'}
          </p>
          {!isViewer && !searchQuery && statusFilter === 'all' && (
            <Button
              onClick={() => setIsUploadModalOpen(true)}
              className="mt-4 bg-gray-900 text-white hover:bg-gray-800"
              size="sm"
            >
              Upload First Report
            </Button>
          )}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-700">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3">Report Name</th>
                  <th className="px-4 py-3">File</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3">Uploaded By</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredReports.map((report) => (
                  <tr
                    key={report.id}
                    onClick={() => setSelectedReport(report)}
                    className="hover:bg-amber-50/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3.5 font-medium text-gray-900">{report.name}</td>
                    <td className="px-4 py-3.5 text-gray-600 font-mono text-xs">
                      <span className="bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200 uppercase font-semibold text-[10px] mr-1.5">
                        {report.file_type}
                      </span>
                      {report.file_name}
                    </td>
                    <td className="px-4 py-3.5 text-gray-500 text-xs">{formatBytes(report.file_size)}</td>
                    <td className="px-4 py-3.5 text-gray-600 text-xs">
                      {report.uploaded_by_email || 'Field Staff'}
                    </td>
                    <td className="px-4 py-3.5 text-gray-500 text-xs">{formatDate(report.uploaded_at)}</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border font-medium uppercase text-[10px] ${
                          statusStyles[report.status] || 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {report.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedReport(report)
                        }}
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

      {/* Upload Report Modal */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Upload Field Report</h2>
              <button
                type="button"
                onClick={() => setIsUploadModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {uploadError && (
              <div role="alert" className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                {uploadError}
              </div>
            )}

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Report Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Daily Progress Report — 19 May"
                  value={reportName}
                  onChange={(e) => setReportName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Filename <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="Daily_Report_19_May.pdf"
                    value={fileName}
                    onChange={(e) => setFileName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">File Type</label>
                  <select
                    value={fileType}
                    onChange={(e) => setFileType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
                  >
                    <option value="pdf">PDF Document (.pdf)</option>
                    <option value="xlsx">Excel Spreadsheet (.xlsx)</option>
                    <option value="csv">CSV Data (.csv)</option>
                    <option value="txt">Text Report (.txt)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Simulated File Size (bytes)</label>
                <input
                  type="number"
                  value={fileSize}
                  onChange={(e) => setFileSize(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                />
                <p className="text-[11px] text-gray-400 mt-1">Formatted: {formatBytes(fileSize)}</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Ingestion Source</label>
                <input
                  type="text"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900"
                />
              </div>

              <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsUploadModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={uploadMutation.isPending}
                  size="sm"
                  className="bg-gray-900 text-white hover:bg-gray-800"
                >
                  {uploadMutation.isPending ? 'Uploading…' : 'Submit Report'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Report Detail Drawer */}
      {selectedReport && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-xs">
          <div className="bg-white w-full max-w-md h-full shadow-2xl border-l border-gray-200 flex flex-col overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-gray-200 flex items-start justify-between bg-gray-50">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  Field Report
                </span>
                <h2 className="text-lg font-bold text-gray-900 mt-2">{selectedReport.name}</h2>
                <p className="text-xs text-gray-500 font-mono mt-0.5">{selectedReport.file_name}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedReport(null)}
                className="text-gray-400 hover:text-gray-600 font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Metadata Body */}
            <div className="p-6 space-y-5 flex-1">
              <div className="space-y-3 bg-gray-50 p-4 rounded-lg border border-gray-100 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">File Type:</span>
                  <span className="font-semibold text-gray-900 uppercase">{selectedReport.file_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">File Size:</span>
                  <span className="font-semibold text-gray-900">{formatBytes(selectedReport.file_size)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Source:</span>
                  <span className="font-semibold text-gray-900">{selectedReport.source}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Uploaded By:</span>
                  <span className="font-semibold text-gray-900">
                    {selectedReport.uploaded_by_email || 'Field Staff'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Uploaded Date:</span>
                  <span className="font-semibold text-gray-900">{formatDate(selectedReport.uploaded_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Processing Status:</span>
                  <span
                    className={`font-semibold uppercase text-[10px] px-1.5 py-0.5 rounded border ${
                      statusStyles[selectedReport.status] || 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {selectedReport.status}
                  </span>
                </div>
              </div>

              {/* Extracted Field Events section */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                    Field Events ({linkedEventsData?.total ?? 0})
                  </h3>
                </div>

                {isLoadingLinkedEvents ? (
                  <p className="text-xs text-gray-400">Loading linked events…</p>
                ) : (linkedEventsData?.events ?? []).length === 0 ? (
                  <div className="p-4 bg-gray-50 rounded border border-gray-200 text-center">
                    <p className="text-xs text-gray-500 font-medium">No field events extracted yet.</p>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      Events will appear here once extracted or manually associated.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {linkedEventsData?.events.map((evt) => (
                      <div
                        key={evt.id}
                        className="p-3 bg-gray-50 border border-gray-200 rounded text-xs hover:border-gray-300 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-gray-900">{evt.event_type}</span>
                          <span className="text-amber-700 font-bold">{evt.progress_percent}%</span>
                        </div>
                        <p className="text-gray-600 line-clamp-2">{evt.description}</p>
                        <div className="flex items-center gap-2 text-[10px] text-gray-400 mt-2">
                          <span>{evt.discipline}</span>
                          <span>•</span>
                          <span>{evt.location}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
              {currentRole === 'admin' && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => deleteMutation.mutate(selectedReport.id)}
                  disabled={deleteMutation.isPending}
                  className="text-xs"
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Delete Report'}
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedReport(null)}
                className="ml-auto text-xs"
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
