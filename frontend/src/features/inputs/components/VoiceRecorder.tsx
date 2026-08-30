/**
 * VoiceRecorder — Construction audio note recording and STT submission component.
 * Uses browser MediaRecorder API with full lifecycle states (idle, recording, stopped, uploading, unsupported).
 */

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { uploadMediaInput } from '../api'
import type { FieldInput } from '../types'

interface VoiceRecorderProps {
  projectId: string
  onSuccess: (input: FieldInput) => void
  onCancel: () => void
}

type RecorderState =
  | 'idle'
  | 'recording'
  | 'stopped'
  | 'uploading'
  | 'unsupported'

export function VoiceRecorder({ projectId, onSuccess, onCancel }: VoiceRecorderProps) {
  const [recorderState, setRecorderState] = useState<RecorderState>(() => {
    if (typeof window === 'undefined' || !navigator.mediaDevices || typeof MediaRecorder === 'undefined') {
      return 'unsupported'
    }
    return 'idle'
  })
  const [title, setTitle] = useState('')
  const [fieldDate, setFieldDate] = useState(new Date().toISOString().split('T')[0])
  const [durationSeconds, setDurationSeconds] = useState(0)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const timerIntervalRef = useRef<number | null>(null)

  const queryClient = useQueryClient()

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [audioUrl])

  const mutation = useMutation({
    mutationFn: () => {
      if (!audioBlob) {
        throw new Error('No recorded audio available to upload.')
      }
      return uploadMediaInput(projectId, {
        file: audioBlob,
        input_type: 'voice',
        filename: `voice_note_${Date.now()}.webm`,
        title: title.trim() || undefined,
        field_date: fieldDate || undefined,
      })
    },
    onSuccess: (newInput) => {
      queryClient.invalidateQueries({ queryKey: ['field-inputs', projectId] })
      onSuccess(newInput)
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : 'Voice submission failed')
      setRecorderState('stopped')
    },
  })

  const startRecording = async () => {
    setError(null)
    audioChunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data)
        }
      }

      recorder.onstop = () => {
        const mimeType = recorder.mimeType || 'audio/webm'
        const blob = new Blob(audioChunksRef.current, { type: mimeType })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        setRecorderState('stopped')

        // Stop all audio tracks
        stream.getTracks().forEach((track) => track.stop())
      }

      recorder.start(250) // collect chunks every 250ms
      setRecorderState('recording')
      setDurationSeconds(0)

      timerIntervalRef.current = window.setInterval(() => {
        setDurationSeconds((prev) => prev + 1)
      }, 1000)
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? `Microphone access denied: ${err.message}`
          : 'Unable to access microphone'
      )
      setRecorderState('idle')
    }
  }

  const stopRecording = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
  }

  const resetRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
    }
    setAudioBlob(null)
    setAudioUrl(null)
    setDurationSeconds(0)
    setRecorderState('idle')
    setError(null)
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!audioBlob) {
      setError('Please record an audio note first.')
      return
    }

    setRecorderState('uploading')
    mutation.mutate()
  }

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60)
      .toString()
      .padStart(2, '0')
    const s = (secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  if (recorderState === 'unsupported') {
    return (
      <div className="p-6 text-center space-y-4 bg-amber-50 border border-amber-200 rounded-lg">
        <div className="text-amber-800 font-semibold text-sm">
          🎙️ Audio Recording Unsupported
        </div>
        <p className="text-xs text-amber-700 max-w-sm mx-auto">
          Your current browser or environment does not support the HTML5 MediaRecorder audio capture API.
          Please use a modern browser with microphone permissions or submit text/photo updates instead.
        </p>
        <Button variant="outline" size="sm" onClick={onCancel}>
          Back
        </Button>
      </div>
    )
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
          <label htmlFor="voice-title" className="block text-xs font-medium text-gray-700 mb-1">
            Voice Note Title (Optional)
          </label>
          <input
            id="voice-title"
            type="text"
            placeholder="e.g. End of Day Site Debrief"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            disabled={recorderState === 'recording' || mutation.isPending}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>

        <div>
          <label htmlFor="voice-date" className="block text-xs font-medium text-gray-700 mb-1">
            Field Date
          </label>
          <input
            id="voice-date"
            type="date"
            value={fieldDate}
            onChange={(e) => setFieldDate(e.target.value)}
            disabled={recorderState === 'recording' || mutation.isPending}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 focus:ring-1 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
      </div>

      {/* Recording Stage Panel */}
      <div className="p-6 bg-gray-50 border border-gray-200 rounded-lg flex flex-col items-center justify-center space-y-4">
        {recorderState === 'idle' && (
          <div className="text-center space-y-3">
            <div className="h-16 w-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto text-amber-700 text-2xl font-bold">
              🎙️
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Ready to Record Voice Note</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Speak clearly regarding construction progress, equipment, or constraints.
              </p>
            </div>
            <Button
              type="button"
              onClick={startRecording}
              className="bg-amber-700 hover:bg-amber-800 text-white font-medium px-5"
            >
              Start Recording
            </Button>
          </div>
        )}

        {recorderState === 'recording' && (
          <div className="text-center space-y-3">
            <div className="flex items-center justify-center gap-2">
              <span className="h-3 w-3 rounded-full bg-red-600 animate-ping" />
              <span className="text-xs font-bold uppercase tracking-wider text-red-600">Recording</span>
            </div>
            <div className="text-3xl font-mono font-bold text-gray-900 tracking-wider">
              {formatTimer(durationSeconds)}
            </div>
            <Button
              type="button"
              variant="destructive"
              onClick={stopRecording}
              className="px-6 font-medium"
            >
              ■ Stop Recording
            </Button>
          </div>
        )}

        {recorderState === 'stopped' && audioUrl && (
          <div className="w-full space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-700">Audio Preview ({formatTimer(durationSeconds)})</span>
              <button
                type="button"
                onClick={resetRecording}
                className="text-xs font-medium text-amber-700 hover:text-amber-900"
              >
                ↻ Re-record
              </button>
            </div>

            <audio controls src={audioUrl} className="w-full h-10" />

            <div className="p-2.5 bg-blue-50 border border-blue-100 rounded text-[11px] text-blue-700">
              💡 Submitting will upload the audio and automatically run Whisper Speech-to-Text transcription.
            </div>
          </div>
        )}

        {recorderState === 'uploading' && (
          <div className="text-center space-y-2 py-4">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-2" />
            <p className="text-sm font-semibold text-gray-900">Uploading & Transcribing…</p>
            <p className="text-xs text-gray-500">Storing audio in Supabase Storage and generating Whisper transcript.</p>
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          disabled={recorderState === 'recording' || mutation.isPending}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          disabled={!audioBlob || recorderState === 'recording' || mutation.isPending}
          className="bg-gray-900 text-white hover:bg-gray-800"
        >
          {mutation.isPending ? 'Transcribing…' : 'Submit & Transcribe'}
        </Button>
      </div>
    </form>
  )
}
