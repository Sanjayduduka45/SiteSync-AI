/**
 * Unit tests for VoiceRecorder component.
 * Validates audio recording lifecycle, state transitions, preview, and error handling.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { VoiceRecorder } from '@/features/inputs/components/VoiceRecorder'
import * as inputsApi from '@/features/inputs/api'

class MockMediaRecorder {
  state: 'inactive' | 'recording' | 'paused' = 'inactive'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  mimeType = 'audio/webm'

  start() {
    this.state = 'recording'
  }

  stop() {
    this.state = 'inactive'
    if (this.ondataavailable) {
      this.ondataavailable({ data: new Blob(['mock audio'], { type: 'audio/webm' }) })
    }
    if (this.onstop) {
      this.onstop()
    }
  }
}

function renderVoiceRecorder(props = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  const defaultProps = {
    projectId: 'proj-mtp-001',
    onSuccess: vi.fn(),
    onCancel: vi.fn(),
    ...props,
  }

  return render(
    <QueryClientProvider client={queryClient}>
      <VoiceRecorder {...defaultProps} />
    </QueryClientProvider>
  )
}

describe('VoiceRecorder', () => {
  beforeEach(() => {
    vi.stubGlobal('MediaRecorder', MockMediaRecorder)
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    })
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-audio-url')
    window.URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders initial idle state with start recording button', () => {
    renderVoiceRecorder()

    expect(screen.getByText(/Ready to Record Voice Note/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Start Recording/i })).toBeInTheDocument()
  })

  it('transitions to recording state on start click and stops on stop click', async () => {
    renderVoiceRecorder()

    const startBtn = screen.getByRole('button', { name: /Start Recording/i })
    fireEvent.click(startBtn)

    await waitFor(() => {
      expect(screen.getByText('Recording')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Stop Recording/i })).toBeInTheDocument()
    })

    const stopBtn = screen.getByRole('button', { name: /Stop Recording/i })
    fireEvent.click(stopBtn)

    await waitFor(() => {
      expect(screen.getByText(/Audio Preview/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Submit & Transcribe/i })).toBeInTheDocument()
    })
  })

  it('submits recorded audio successfully', async () => {
    const uploadSpy = vi.spyOn(inputsApi, 'uploadMediaInput').mockResolvedValue({
      id: 'inp-01',
      project_id: 'proj-mtp-001',
      submitted_by: 'user-01',
      input_type: 'voice',
      raw_text: 'Transcribed text',
      media_path: 'projects/proj-mtp-001/inputs/inp-01/audio.webm',
      media_size_bytes: 1024,
      transcription_status: 'completed',
      field_date: '2026-08-30',
      metadata: {},
      created_at: '2026-08-30T10:00:00Z',
      updated_at: '2026-08-30T10:00:00Z',
    })

    const onSuccess = vi.fn()
    renderVoiceRecorder({ onSuccess })

    fireEvent.click(screen.getByRole('button', { name: /Start Recording/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Stop Recording/i })).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Stop Recording/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Submit & Transcribe/i })).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Submit & Transcribe/i }))

    await waitFor(() => {
      expect(uploadSpy).toHaveBeenCalledWith(
        'proj-mtp-001',
        expect.objectContaining({
          input_type: 'voice',
        })
      )
      expect(onSuccess).toHaveBeenCalled()
    })
  })

  it('renders unsupported message when MediaRecorder is unavailable', () => {
    vi.stubGlobal('MediaRecorder', undefined)
    renderVoiceRecorder()

    expect(screen.getByText(/Audio Recording Unsupported/i)).toBeInTheDocument()
  })

  it('displays error when microphone permission is denied', async () => {
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn().mockRejectedValue(new Error('Permission denied')),
      },
    })

    renderVoiceRecorder()
    fireEvent.click(screen.getByRole('button', { name: /Start Recording/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Microphone access denied/i)
    })
  })
})
