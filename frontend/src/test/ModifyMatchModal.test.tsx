/**
 * Tests for ModifyMatchModal component.
 */

import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'
import { ModifyMatchModal } from '@/features/decisions/components/ModifyMatchModal'

vi.mock('@/features/schedules/api', () => ({
  getScheduleActivities: vi.fn().mockResolvedValue({
    items: [
      {
        id: 'act-1',
        activity_code: 'ACT-101',
        name: 'Structural Steel Tier 1',
        discipline: 'Civil',
      },
      {
        id: 'act-2',
        activity_code: 'ACT-202',
        name: 'Underground Sewer Piping',
        discipline: 'Piping',
      },
    ],
    total: 2,
    limit: 100,
    offset: 0,
  }),
}))

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

describe('ModifyMatchModal', () => {
  it('does not render when isOpen is false', () => {
    renderWithQuery(
      <ModifyMatchModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={false}
        projectId="proj-1"
        initialActivityId="act-1"
      />
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders and prepopulates initial recommendation values', () => {
    renderWithQuery(
      <ModifyMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={false}
        projectId="proj-1"
        initialActivityId="act-1"
        initialActivityName="Structural Steel Tier 1"
        initialQuantity={12.5}
        initialUnit="tons"
        initialDate="2026-08-30"
        initialNotes=""
      />
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByDisplayValue('12.5')).toBeInTheDocument()
    expect(screen.getByDisplayValue('tons')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2026-08-30')).toBeInTheDocument()
  })

  it('rejects negative quantity validation error', async () => {
    const onConfirm = vi.fn()
    renderWithQuery(
      <ModifyMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        isSubmitting={false}
        projectId="proj-1"
        initialActivityId="act-1"
        initialQuantity={10}
        initialDate="2026-08-30"
      />
    )

    const qtyInput = screen.getByLabelText(/Actual Quantity/i)
    await userEvent.clear(qtyInput)
    await userEvent.type(qtyInput, '-5')

    const submitBtn = screen.getByRole('button', { name: /Save & Approve Changes/i })
    await userEvent.click(submitBtn)

    expect(
      screen.getByText(/Quantity must be a non-negative number \(>= 0\)/i)
    ).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('submits updated payload with trimmed fields on valid form submit', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined)
    renderWithQuery(
      <ModifyMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        isSubmitting={false}
        projectId="proj-1"
        initialActivityId="act-1"
        initialQuantity={10}
        initialUnit="spools"
        initialDate="2026-08-30"
      />
    )

    const qtyInput = screen.getByLabelText(/Actual Quantity/i)
    await userEvent.clear(qtyInput)
    await userEvent.type(qtyInput, '15.5')

    const notesInput = screen.getByLabelText(/Planner Notes \/ Clarification/i)
    await userEvent.type(notesInput, '  Verified quantity with site engineer  ')

    const submitBtn = screen.getByRole('button', { name: /Save & Approve Changes/i })
    await userEvent.click(submitBtn)

    expect(onConfirm).toHaveBeenCalledWith({
      schedule_activity_id: 'act-1',
      actual_quantity: 15.5,
      actual_unit: 'spools',
      actual_date: '2026-08-30',
      notes: 'Verified quantity with site engineer',
    })
  })

  it('shows loading state during submission', () => {
    renderWithQuery(
      <ModifyMatchModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        isSubmitting={true}
        projectId="proj-1"
        initialActivityId="act-1"
      />
    )

    expect(screen.getByText('Saving changes…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Saving changes…/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeDisabled()
  })

  it('closes on Escape key', () => {
    const onClose = vi.fn()
    renderWithQuery(
      <ModifyMatchModal
        isOpen={true}
        onClose={onClose}
        onConfirm={vi.fn()}
        isSubmitting={false}
        projectId="proj-1"
        initialActivityId="act-1"
      />
    )

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
