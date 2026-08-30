/**
 * TextInputForm — Raw text field notes submission form.
 */

import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { createTextInput } from '../api'
import type { FieldInput } from '../types'

interface TextInputFormProps {
  projectId: string
  onSuccess: (input: FieldInput) => void
  onCancel: () => void
}

export function TextInputForm({ projectId, onSuccess, onCancel }: TextInputFormProps) {
  const [title, setTitle] = useState('')
  const [rawText, setRawText] = useState('')
  const [fieldDate, setFieldDate] = useState(new Date().toISOString().split('T')[0])
  const [error, setError] = useState<string | null>(null)

  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      createTextInput(projectId, {
        title: title.trim() || undefined,
        raw_text: rawText.trim(),
        field_date: fieldDate || undefined,
      }),
    onSuccess: (newInput) => {
      queryClient.invalidateQueries({ queryKey: ['field-inputs', projectId] })
      onSuccess(newInput)
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to submit text update')
    },
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!rawText.trim()) {
      setError('Field notes text is required and cannot be blank.')
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
          <label htmlFor="text-title" className="block text-xs font-medium text-gray-700 mb-1">
            Note Title (Optional)
          </label>
          <input
            id="text-title"
            type="text"
            placeholder="e.g. Unit 1 Piping Daily Progress"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div>
          <label htmlFor="text-date" className="block text-xs font-medium text-gray-700 mb-1">
            Field Date <span className="text-red-500">*</span>
          </label>
          <input
            id="text-date"
            type="date"
            value={fieldDate}
            onChange={(e) => setFieldDate(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
      </div>

      <div>
        <label htmlFor="text-raw-content" className="block text-xs font-medium text-gray-700 mb-1">
          Field Notes / Observations <span className="text-red-500">*</span>
        </label>
        <textarea
          id="text-raw-content"
          rows={5}
          placeholder="Describe physical work, progress percentages, crew activities, equipment delays, or site blockers..."
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500 font-sans"
        />
        <p className="text-[11px] text-gray-400 mt-1">
          Enter raw observations as noted on site.
        </p>
      </div>

      <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={mutation.isPending}>
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={mutation.isPending}
          className="bg-gray-900 text-white hover:bg-gray-800"
        >
          {mutation.isPending ? 'Saving Notes…' : 'Submit Field Notes'}
        </Button>
      </div>
    </form>
  )
}
