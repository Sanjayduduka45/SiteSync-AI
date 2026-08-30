/**
 * DocumentUploadForm — Field document / spreadsheet / checklist upload component.
 */

import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { uploadMediaInput } from '../api'
import type { FieldInput } from '../types'

interface DocumentUploadFormProps {
  projectId: string
  onSuccess: (input: FieldInput) => void
  onCancel: () => void
}

const MAX_DOCUMENT_SIZE = 25 * 1024 * 1024 // 25 MB
const ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.txt', '.xlsx', '.xls', '.csv']

export function DocumentUploadForm({ projectId, onSuccess, onCancel }: DocumentUploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [fieldDate, setFieldDate] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) {
        throw new Error('Please select a document to upload.')
      }
      return uploadMediaInput(projectId, {
        file: selectedFile,
        input_type: 'document',
        title: title.trim() || undefined,
        raw_text: notes.trim() || undefined,
        field_date: fieldDate || undefined,
      })
    },
    onSuccess: (newInput) => {
      queryClient.invalidateQueries({ queryKey: ['field-inputs', projectId] })
      onSuccess(newInput)
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : 'Document upload failed')
    },
  })

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError(null)
    const file = e.target.files?.[0]
    if (!file) return

    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`
    if (!ALLOWED_DOCUMENT_EXTENSIONS.includes(ext)) {
      setError(`Invalid format: ${ext}. Allowed: PDF, XLSX, CSV, and TXT files.`)
      return
    }

    if (file.size > MAX_DOCUMENT_SIZE) {
      setError(`Document exceeds maximum size of 25 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB).`)
      return
    }

    setSelectedFile(file)
  }

  const handleClearFile = () => {
    setSelectedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!selectedFile) {
      setError('Please select a document file.')
      return
    }

    mutation.mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-2">
          <label htmlFor="doc-title" className="block text-xs font-medium text-gray-700 mb-1">
            Document Title (Optional)
          </label>
          <input
            id="doc-title"
            type="text"
            placeholder="e.g. Substation Cable Pulling Log"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div>
          <label htmlFor="doc-date" className="block text-xs font-medium text-gray-700 mb-1">
            Field Date
          </label>
          <input
            id="doc-date"
            type="date"
            value={fieldDate}
            onChange={(e) => setFieldDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
      </div>

      {/* File Dropzone */}
      {!selectedFile ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400 hover:bg-gray-50 transition-colors"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.xlsx,.xls,.csv"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="text-3xl mb-2">📁</div>
          <p className="text-sm font-semibold text-gray-800">Click to select site document</p>
          <p className="text-xs text-gray-500 mt-1">PDF, Excel, CSV, or Text files up to 25 MB</p>
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 bg-amber-100 rounded text-amber-800 flex items-center justify-center font-bold text-sm uppercase">
              {selectedFile.name.split('.').pop()}
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900 truncate max-w-xs">{selectedFile.name}</p>
              <p className="text-xs text-gray-500">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClearFile}
            className="text-xs text-red-600 hover:text-red-800 font-medium"
          >
            Remove
          </button>
        </div>
      )}

      <div>
        <label htmlFor="doc-notes" className="block text-xs font-medium text-gray-700 mb-1">
          Document Description / Summary (Optional)
        </label>
        <textarea
          id="doc-notes"
          rows={3}
          placeholder="Summary of document contents, contractor sign-off, or relevant progress milestones..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500 font-sans"
        />
      </div>

      <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={mutation.isPending}>
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={!selectedFile || mutation.isPending}
          className="bg-gray-900 text-white hover:bg-gray-800"
        >
          {mutation.isPending ? 'Uploading…' : 'Upload Document'}
        </Button>
      </div>
    </form>
  )
}
