import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { AuditFilterBar } from '@/features/audit/components/AuditFilterBar'

describe('AuditFilterBar', () => {
  it('renders filter inputs and triggers callback when event type changes', async () => {
    const onFilterChange = vi.fn()
    const onReset = vi.fn()

    render(
      <AuditFilterBar
        filters={{ event_type: 'all', limit: 50, offset: 0 }}
        onFilterChange={onFilterChange}
        onReset={onReset}
      />
    )

    expect(screen.getByLabelText(/Event Type/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Entity Type/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/From Date/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/To Date/i)).toBeInTheDocument()

    const select = screen.getByLabelText(/Event Type/i)
    await userEvent.selectOptions(select, 'APPROVED_ACTUAL_COMMITTED')

    expect(onFilterChange).toHaveBeenCalledWith({
      event_type: 'APPROVED_ACTUAL_COMMITTED',
    })
  })

  it('renders Clear filters button when filters are active and calls onReset on click', async () => {
    const onFilterChange = vi.fn()
    const onReset = vi.fn()

    render(
      <AuditFilterBar
        filters={{ event_type: 'FIELD_INPUT_SUBMITTED', entity_type: 'field_input', limit: 50, offset: 0 }}
        onFilterChange={onFilterChange}
        onReset={onReset}
      />
    )

    const clearBtn = screen.getByRole('button', { name: /Clear filters/i })
    expect(clearBtn).toBeInTheDocument()

    await userEvent.click(clearBtn)
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
