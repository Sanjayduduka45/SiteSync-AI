/**
 * PhotoUploadForm — Site photo capture and progress upload component.
 */

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { uploadMediaInput } from '../api'
import type { FieldInput } from '../types'

interface PhotoUploadFormProps {
  projectId: string
  onSuccess: (input: FieldInput) => void
  onCancel: () => void
}

const MAX_PHOTO_SIZE = 15 * 1024 * 1024 // 15 MB
const ALLOWED_PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

export function PhotoUploadForm({ projectId, onSuccess, onCancel }: PhotoUploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [fieldDate, setFieldDate] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const mutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) {
        throw new Error('Please select an image file to upload.')
      }
      return uploadMediaInput(projectId, {
        file: selectedFile,
        input_type: 'photo',
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
      setError(err instanceof Error ? err.message : 'Photo upload failed')
    },
  })

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError(null)
    const file = e.target.files?.[0]
    if (!file) return

    // Extension check
    const ext = `.${file.name.split('.').pop()?.toLowerCase()}`
    if (!ALLOWED_PHOTO_EXTENSIONS.includes(ext)) {
      setError(`Invalid format: ${ext}. Only JPG, PNG, and WebP photos are permitted.`)
      return
    }

    // Size check
    if (file.size > MAX_PHOTO_SIZE) {
      setError(`Image exceeds maximum size of 15 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB).`)
      return
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }

    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
  }

  const handleClearFile = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setSelectedFile(null)
    setPreviewUrl(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!selectedFile) {
      setError('Please select or capture a site photo.')
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
          <label htmlFor="photo-title" className="block text-xs font-medium text-gray-700 mb-1">
            Photo Caption / Location
          </label>
          <input
            id="photo-title"
            type="text"
            placeholder="e.g. Unit 1 Header Weld Root Pass"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div>
          <label htmlFor="photo-date" className="block text-xs font-medium text-gray-700 mb-1">
            Field Date
          </label>
          <input
            id="photo-date"
            type="date"
            value={fieldDate}
            onChange={(e) => setFieldDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
      </div>

      {/* File Upload / Preview Dropzone */}
      {!selectedFile ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400 hover:bg-gray-50 transition-colors"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            className="hidden"
          />
          <div className="text-3xl mb-2">📷</div>
          <p className="text-sm font-semibold text-gray-800">Click to select site photo</p>
          <p className="text-xs text-gray-500 mt-1">JPEG, PNG, or WebP up to 15 MB</p>
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-700 truncate max-w-xs">{selectedFile.name}</span>
            <button
              type="button"
              onClick={handleClearFile}
              className="text-xs text-red-600 hover:text-red-800 font-medium"
            >
              Remove
            </button>
          </div>
          {previewUrl && (
            <div className="relative max-h-56 overflow-hidden rounded border border-gray-200 bg-black/5 flex items-center justify-center">
              <img src={previewUrl} alt="Preview" className="max-h-56 object-contain" />
            </div>
          )}
          <p className="text-[11px] text-gray-400">
            Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
          </p>
        </div>
      )}

      <div>
        <label htmlFor="photo-notes" className="block text-xs font-medium text-gray-700 mb-1">
          Accompanying Notes (Optional)
        </label>
        <textarea
          id="photo-notes"
          rows={3}
          placeholder="Add context, equipment tag, or defect observations regarding this photo..."
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
          {mutation.isPending ? 'Uploading…' : 'Upload Photo'}
        </Button>
      </div>
    </form>
  )
}
