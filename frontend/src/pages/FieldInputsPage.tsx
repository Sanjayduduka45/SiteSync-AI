/**
 * FieldInputsPage — Primary multi-modal field input capture and feed interface.
 * Route: /inputs
 * Phase 5: Displays AI extraction status on feed cards and connects to InputDetailDrawer.
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { useProject } from '@/features/projects/useProject'
import { deleteFieldInput, fetchFieldInputs } from '@/features/inputs/api'
import { getProjectExtractions } from '@/features/extractions/api'
import type { ExtractionRecord } from '@/features/extractions/types'
import type { FieldInput, FieldInputType } from '@/features/inputs/types'
import { TextInputForm } from '@/features/inputs/components/TextInputForm'
import { VoiceRecorder } from '@/features/inputs/components/VoiceRecorder'
import { PhotoUploadForm } from '@/features/inputs/components/PhotoUploadForm'
import { DocumentUploadForm } from '@/features/inputs/components/DocumentUploadForm'
import { InputDetailDrawer } from '@/features/inputs/components/InputDetailDrawer'

type ModalTab = 'text' | 'voice' | 'photo' | 'document'

export default function FieldInputsPage() {
  const { selectedProject, selectedProjectId, currentRole } = useProject()
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [dateFilter, setDateFilter] = useState<string>('')
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false)
  const [activeModalTab, setActiveModalTab] = useState<ModalTab>('text')
  const [selectedInput, setSelectedInput] = useState<FieldInput | null>(null)

  const queryClient = useQueryClient()
  const isViewer = currentRole === 'viewer'

  const {
    data: inputsData,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['field-inputs', selectedProjectId, typeFilter, dateFilter],
    queryFn: () =>
      fetchFieldInputs(selectedProjectId!, {
        input_type: typeFilter !== 'all' ? typeFilter : undefined,
        field_date: dateFilter || undefined,
      }),
    enabled: Boolean(selectedProjectId),
  })

  // Fetch project-level extractions to decorate feed cards without N+1 requests
  const { data: projectExtractionsData } = useQuery({
    queryKey: ['project-extractions', selectedProjectId],
    queryFn: () => getProjectExtractions(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  const extractionsByInputId = (projectExtractionsData?.extractions ?? []).reduce<Record<string, ExtractionRecord>>(
    (acc, ext) => {
      acc[ext.field_input_id] = ext
      return acc
    },
    {}
  )

  const deleteMutation = useMutation({
    mutationFn: (inputId: string) => deleteFieldInput(selectedProjectId!, inputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['field-inputs', selectedProjectId] })
      queryClient.invalidateQueries({ queryKey: ['project-extractions', selectedProjectId] })
      if (selectedInput) {
        setSelectedInput(null)
      }
    },
  })

  const allInputs = inputsData?.inputs ?? []
  const filteredInputs = allInputs.filter((inp) => {
    const q = searchQuery.toLowerCase().trim()
    if (!q) return true
    return (
      (inp.title && inp.title.toLowerCase().includes(q)) ||
      (inp.raw_text && inp.raw_text.toLowerCase().includes(q)) ||
      (inp.submitted_by_email && inp.submitted_by_email.toLowerCase().includes(q)) ||
      (inp.media_filename && inp.media_filename.toLowerCase().includes(q))
    )
  })

  const typeConfig: Record<FieldInputType, { label: string; icon: string; style: string }> = {
    text: { label: 'Text Note', icon: '📝', style: 'bg-blue-50 text-blue-700 border-blue-200' },
    voice: { label: 'Voice Note', icon: '🎙️', style: 'bg-amber-50 text-amber-700 border-amber-200' },
    photo: { label: 'Photo', icon: '📷', style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    document: { label: 'Document', icon: '📁', style: 'bg-purple-50 text-purple-700 border-purple-200' },
  }

  const handleCreated = (newInput: FieldInput) => {
    setIsSubmitModalOpen(false)
    setSelectedInput(newInput)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Field Inputs</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Capture raw construction progress, voice logs, photos, and site documents for{' '}
            <span className="font-semibold text-gray-700">{selectedProject?.projectName ?? 'Project'}</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={() => {
              setActiveModalTab('text')
              setIsSubmitModalOpen(true)
            }}
            disabled={isViewer || !selectedProjectId}
            className="bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-40"
          >
            Submit Field Update
          </Button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        <div className="w-full md:w-80">
          <input
            type="text"
            placeholder="Search notes, audio transcripts, authors…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-500 uppercase">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-2.5 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="all">All Types</option>
              <option value="text">Text Notes</option>
              <option value="voice">Voice Recordings</option>
              <option value="photo">Photos</option>
              <option value="document">Documents</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-500 uppercase">Date:</span>
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
            {dateFilter && (
              <button
                type="button"
                onClick={() => setDateFilter('')}
                className="text-xs text-gray-400 hover:text-gray-600 font-bold"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Feed & Content Area */}
      {isLoading ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-3" />
          <p className="text-sm text-gray-500 font-medium">Loading field inputs…</p>
        </div>
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-sm font-medium text-red-800">
            {error instanceof Error ? error.message : 'Failed to load field inputs.'}
          </p>
        </div>
      ) : filteredInputs.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="h-10 w-10 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3 text-gray-400 font-bold text-lg">
            📋
          </div>
          <h3 className="text-base font-semibold text-gray-900">No field inputs captured.</h3>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            {searchQuery || typeFilter !== 'all' || dateFilter
              ? 'No submissions matched your search filters.'
              : 'Record voice debriefs, notes, or site photos to log raw progress from the field.'}
          </p>
          {!isViewer && !searchQuery && typeFilter === 'all' && !dateFilter && (
            <Button
              onClick={() => {
                setActiveModalTab('text')
                setIsSubmitModalOpen(true)
              }}
              className="mt-4 bg-gray-900 text-white hover:bg-gray-800"
              size="sm"
            >
              Submit First Field Update
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredInputs.map((input) => {
            const config = typeConfig[input.input_type] || {
              label: input.input_type,
              icon: '📄',
              style: 'bg-gray-50 text-gray-700 border-gray-200',
            }

            const extraction = extractionsByInputId[input.id]

            return (
              <div
                key={input.id}
                onClick={() => setSelectedInput(input)}
                className="bg-white rounded-lg border border-gray-200 p-4 shadow-xs hover:border-amber-400/80 hover:shadow-md cursor-pointer transition-all flex flex-col justify-between"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex flex-wrap items-center justify-between gap-1.5 mb-2">
                    <span
                      className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${config.style}`}
                    >
                      <span>{config.icon}</span> {config.label}
                    </span>

                    <div className="flex items-center gap-1">
                      {input.input_type === 'voice' && (
                        <span
                          className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                            input.transcription_status === 'completed'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : input.transcription_status === 'failed'
                              ? 'bg-red-50 text-red-700 border-red-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}
                        >
                          {input.transcription_status}
                        </span>
                      )}

                      {/* AI Extraction Status Badge */}
                      {extraction?.status === 'completed' ? (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border bg-emerald-50 text-emerald-700 border-emerald-200 flex items-center gap-1">
                          <span>✨</span> Extracted{' '}
                          {extraction.confidence_score !== null
                            ? `(${Math.round(extraction.confidence_score * 100)}%)`
                            : ''}
                        </span>
                      ) : extraction?.status === 'pending' ? (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                          Extracting…
                        </span>
                      ) : extraction?.status === 'failed' ? (
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border bg-red-50 text-red-700 border-red-200">
                          Extraction Failed
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium text-gray-500 px-1.5 py-0.5 rounded border bg-gray-50 border-gray-200">
                          Unprocessed
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Title & snippet */}
                  <h3 className="text-sm font-bold text-gray-900 line-clamp-1">
                    {input.title || `${config.label} (${input.field_date})`}
                  </h3>

                  {input.raw_text ? (
                    <p className="text-xs text-gray-600 mt-1.5 line-clamp-3 leading-relaxed">
                      {input.raw_text}
                    </p>
                  ) : input.media_filename ? (
                    <p className="text-xs text-gray-500 font-mono mt-1.5 truncate">
                      📎 {input.media_filename}
                    </p>
                  ) : (
                    <p className="text-xs text-gray-400 italic mt-1.5">No text notes provided.</p>
                  )}
                </div>

                {/* Card Footer */}
                <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-400">
                  <span>{input.submitted_by_email || 'Field Staff'}</span>
                  <span>{input.field_date}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Submit Update Modal with 4 Modality Tabs */}
      {isSubmitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6 shadow-xl border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Submit Field Update</h2>
              <button
                type="button"
                onClick={() => setIsSubmitModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {/* Modality Tabs */}
            <div className="flex border-b border-gray-200 mb-4">
              <button
                type="button"
                onClick={() => setActiveModalTab('text')}
                className={`flex-1 py-2 text-xs font-semibold border-b-2 text-center transition-colors ${
                  activeModalTab === 'text'
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📝 Text Note
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('voice')}
                className={`flex-1 py-2 text-xs font-semibold border-b-2 text-center transition-colors ${
                  activeModalTab === 'voice'
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                🎙️ Voice Note
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('photo')}
                className={`flex-1 py-2 text-xs font-semibold border-b-2 text-center transition-colors ${
                  activeModalTab === 'photo'
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📷 Photo
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('document')}
                className={`flex-1 py-2 text-xs font-semibold border-b-2 text-center transition-colors ${
                  activeModalTab === 'document'
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📁 Document
              </button>
            </div>

            {/* Active Tab Form */}
            {activeModalTab === 'text' && (
              <TextInputForm
                projectId={selectedProjectId!}
                onSuccess={handleCreated}
                onCancel={() => setIsSubmitModalOpen(false)}
              />
            )}
            {activeModalTab === 'voice' && (
              <VoiceRecorder
                projectId={selectedProjectId!}
                onSuccess={handleCreated}
                onCancel={() => setIsSubmitModalOpen(false)}
              />
            )}
            {activeModalTab === 'photo' && (
              <PhotoUploadForm
                projectId={selectedProjectId!}
                onSuccess={handleCreated}
                onCancel={() => setIsSubmitModalOpen(false)}
              />
            )}
            {activeModalTab === 'document' && (
              <DocumentUploadForm
                projectId={selectedProjectId!}
                onSuccess={handleCreated}
                onCancel={() => setIsSubmitModalOpen(false)}
              />
            )}
          </div>
        </div>
      )}

      {/* Input Detail Slide-over Drawer */}
      {selectedInput && (
        <InputDetailDrawer
          input={selectedInput}
          currentRole={currentRole}
          onClose={() => setSelectedInput(null)}
          onDelete={(inputId) => deleteMutation.mutate(inputId)}
          isDeleting={deleteMutation.isPending}
        />
      )}
    </div>
  )
}
