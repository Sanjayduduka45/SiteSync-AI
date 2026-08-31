/**
 * Tests for RejectMatchModal component.
 */

import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { RejectMatchModal } from '@/features/decisions/components/RejectMatchModal'

describe('RejectMatchModal', () => {
  it('does not render when isOpen is false', () => {
    render(
      <RejectMatchModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={false}
      />
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders modal with target recommendation name when isOpen is true', () => {
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={false}
        recommendedActivityName="ACT-100 — Install Pipe"
      />
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/Reject AI Recommendation/i)).toBeInTheDocument()
    expect(screen.getByText('ACT-100 — Install Pipe')).toBeInTheDocument()
  })

  it('blocks whitespace and empty reasons', async () => {
    const onConfirm = vi.fn()
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        isSubmitting={false}
      />
    )

    const textarea = screen.getByLabelText(/Why are you rejecting this recommendation\?/i)
    const submitBtn = screen.getByRole('button', { name: /Reject Recommendation/i })

    // Button should initially be disabled with empty text
    expect(submitBtn).toBeDisabled()

    // Enter whitespace only
    await userEvent.type(textarea, '     ')
    expect(submitBtn).toBeDisabled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('calls onConfirm with trimmed justification upon valid submission', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined)
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        isSubmitting={false}
      />
    )

    const textarea = screen.getByLabelText(/Why are you rejecting this recommendation\?/i)
    await userEvent.type(textarea, '  Not part of current sprint baseline  ')

    const submitBtn = screen.getByRole('button', { name: /Reject Recommendation/i })
    expect(submitBtn).not.toBeDisabled()

    await userEvent.click(submitBtn)
    expect(onConfirm).toHaveBeenCalledWith('Not part of current sprint baseline')
  })

  it('shows loading state and disables buttons while submitting', () => {
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={true}
      />
    )

    expect(screen.getByText('Rejecting…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Rejecting…/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled()
  })

  it('calls onClose on cancel button click', async () => {
    const onClose = vi.fn()
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        isSubmitting={false}
      />
    )

    await userEvent.click(screen.getByRole('button', { name: /Cancel/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it('closes on Escape key press', () => {
    const onClose = vi.fn()
    render(
      <RejectMatchModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        isSubmitting={false}
      />
    )

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
