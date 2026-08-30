/**
 * InputDetailDrawer — Slide-over drawer displaying raw field input details, media, and transcription.
 */

import { Button } from '@/components/ui/button'
import type { FieldInput } from '../types'

interface InputDetailDrawerProps {
  input: FieldInput | null
  currentRole: string | null
  onClose: () => void
  onDelete?: (inputId: string) => void
  isDeleting?: boolean
}

export function InputDetailDrawer({
  input,
  currentRole,
  onClose,
  onDelete,
  isDeleting,
}: InputDetailDrawerProps) {
  if (!input) return null

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    } catch {
      return iso
    }
  }

  const typeLabels: Record<string, { label: string; icon: string; style: string }> = {
    text: { label: 'Text Note', icon: '📝', style: 'bg-blue-50 text-blue-700 border-blue-200' },
    voice: { label: 'Voice Recording', icon: '🎙️', style: 'bg-amber-50 text-amber-700 border-amber-200' },
    photo: { label: 'Site Photo', icon: '📷', style: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    document: { label: 'Site Document', icon: '📁', style: 'bg-purple-50 text-purple-700 border-purple-200' },
  }

  const badge = typeLabels[input.input_type] || {
    label: input.input_type,
    icon: '📄',
    style: 'bg-gray-50 text-gray-700 border-gray-200',
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-xs">
      <div className="bg-white w-full max-w-lg h-full shadow-2xl border-l border-gray-200 flex flex-col overflow-y-auto">
        {/* Drawer Header */}
        <div className="p-6 border-b border-gray-200 flex items-start justify-between bg-gray-50">
          <div>
            <span
              className={`inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${badge.style}`}
            >
              <span>{badge.icon}</span> {badge.label}
            </span>
            <h2 className="text-lg font-bold text-gray-900 mt-2">
              {input.title || `${badge.label} — ${input.field_date}`}
            </h2>
            <p className="text-xs text-gray-500 font-mono mt-0.5">ID: {input.id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 font-bold p-1 rounded hover:bg-gray-200 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Drawer Body */}
        <div className="p-6 space-y-6 flex-1">
          {/* Metadata Section */}
          <div className="space-y-2 bg-gray-50 p-4 rounded-lg border border-gray-200 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Field Date:</span>
              <span className="font-semibold text-gray-900">{input.field_date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Submitted By:</span>
              <span className="font-semibold text-gray-900">{input.submitted_by_email || 'Field Staff'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Submitted At:</span>
              <span className="font-semibold text-gray-900">{formatDate(input.created_at)}</span>
            </div>
            {input.media_size_bytes > 0 && (
              <div className="flex justify-between">
                <span className="text-gray-500">Attachment Size:</span>
                <span className="font-semibold text-gray-900">{formatBytes(input.media_size_bytes)}</span>
              </div>
            )}
          </div>

          {/* Media Player / Image / Document Preview */}
          {input.input_type === 'voice' && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">Audio Recording</h3>
              {input.media_url ? (
                <div className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                  <audio controls src={input.media_url} className="w-full h-10" />
                </div>
              ) : (
                <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs text-gray-500">
                  Audio file stored in Supabase Storage.
                </div>
              )}

              {/* Transcription status */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-gray-700">Whisper Transcript</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase border ${
                      input.transcription_status === 'completed'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : input.transcription_status === 'failed'
                        ? 'bg-red-50 text-red-700 border-red-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                  >
                    {input.transcription_status}
                  </span>
                </div>

                {input.transcription_error && (
                  <p className="text-xs text-red-600 bg-red-50 p-2.5 rounded border border-red-200">
                    STT Error: {input.transcription_error}
                  </p>
                )}

                {input.raw_text ? (
                  <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-800 leading-relaxed font-sans">
                    {input.raw_text}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 italic">No transcript text available.</p>
                )}
              </div>
            </div>
          )}

          {input.input_type === 'photo' && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">Site Photo</h3>
              {input.media_url ? (
                <div className="rounded-lg border border-gray-200 overflow-hidden bg-black/5 flex items-center justify-center p-2">
                  <img
                    src={input.media_url}
                    alt={input.title || 'Site update photo'}
                    className="max-h-72 object-contain rounded"
                  />
                </div>
              ) : (
                <div className="p-4 bg-gray-50 rounded border border-gray-200 text-xs text-gray-500 text-center">
                  Image path: {input.media_path}
                </div>
              )}
            </div>
          )}

          {input.input_type === 'document' && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">Document Attachment</h3>
              <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-gray-900">{input.media_filename || 'Attachment file'}</p>
                  <p className="text-[11px] text-gray-500 font-mono mt-0.5">{input.media_mime_type}</p>
                </div>
                {input.media_url && (
                  <a
                    href={input.media_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-amber-700 hover:text-amber-900 border border-amber-200 bg-amber-50 px-3 py-1.5 rounded hover:bg-amber-100 transition-colors"
                  >
                    Download File ↗
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Raw Text Notes for Text/Photo/Doc */}
          {input.input_type !== 'voice' && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">Field Notes / Content</h3>
              {input.raw_text ? (
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-800 leading-relaxed font-sans whitespace-pre-wrap">
                  {input.raw_text}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic">No additional notes provided.</p>
              )}
            </div>
          )}
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between">
          {currentRole === 'admin' && onDelete && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => onDelete(input.id)}
              disabled={isDeleting}
              className="text-xs"
            >
              {isDeleting ? 'Deleting…' : 'Delete Input'}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onClose} className="ml-auto text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}
