/**
 * Tests for RiskFilterBar component — SiteSync AI Phase 9.6.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { RiskFilterBar } from '@/features/risk/components/RiskFilterBar'

describe('RiskFilterBar', () => {
  it('renders all filter controls properly', () => {
    render(
      <RiskFilterBar
        severity="all"
        category="all"
        wbsCode=""
        discipline=""
        onSeverityChange={vi.fn()}
        onCategoryChange={vi.fn()}
        onWbsCodeChange={vi.fn()}
        onDisciplineChange={vi.fn()}
        onClearFilters={vi.fn()}
      />
    )

    expect(screen.getByLabelText(/Severity Level/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Risk Category/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/WBS Code/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Discipline/i)).toBeInTheDocument()
  })

  it('triggers onSeverityChange callback when severity dropdown changes', async () => {
    const onSeverityChange = vi.fn()
    render(
      <RiskFilterBar
        severity="all"
        category="all"
        wbsCode=""
        discipline=""
        onSeverityChange={onSeverityChange}
        onCategoryChange={vi.fn()}
        onWbsCodeChange={vi.fn()}
        onDisciplineChange={vi.fn()}
        onClearFilters={vi.fn()}
      />
    )

    const select = screen.getByLabelText(/Severity Level/i)
    await userEvent.selectOptions(select, 'critical')
    expect(onSeverityChange).toHaveBeenCalledWith('critical')
  })

  it('triggers onCategoryChange callback when category dropdown changes', async () => {
    const onCategoryChange = vi.fn()
    render(
      <RiskFilterBar
        severity="all"
        category="all"
        wbsCode=""
        discipline=""
        onSeverityChange={vi.fn()}
        onCategoryChange={onCategoryChange}
        onWbsCodeChange={vi.fn()}
        onDisciplineChange={vi.fn()}
        onClearFilters={vi.fn()}
      />
    )

    const select = screen.getByLabelText(/Risk Category/i)
    await userEvent.selectOptions(select, 'float_erosion')
    expect(onCategoryChange).toHaveBeenCalledWith('float_erosion')
  })

  it('triggers text change callbacks for WBS and Discipline', async () => {
    const onWbsCodeChange = vi.fn()
    const onDisciplineChange = vi.fn()

    render(
      <RiskFilterBar
        severity="all"
        category="all"
        wbsCode=""
        discipline=""
        onSeverityChange={vi.fn()}
        onCategoryChange={vi.fn()}
        onWbsCodeChange={onWbsCodeChange}
        onDisciplineChange={onDisciplineChange}
        onClearFilters={vi.fn()}
      />
    )

    const wbsInput = screen.getByLabelText(/WBS Code/i)
    await userEvent.type(wbsInput, '1.2')
    expect(onWbsCodeChange).toHaveBeenCalled()

    const discInput = screen.getByLabelText(/Discipline/i)
    await userEvent.type(discInput, 'Civil')
    expect(onDisciplineChange).toHaveBeenCalled()
  })

  it('renders Clear Filters button when any filter is active and triggers callback', async () => {
    const onClearFilters = vi.fn()
    render(
      <RiskFilterBar
        severity="critical"
        category="all"
        wbsCode=""
        discipline=""
        onSeverityChange={vi.fn()}
        onCategoryChange={vi.fn()}
        onWbsCodeChange={vi.fn()}
        onDisciplineChange={vi.fn()}
        onClearFilters={onClearFilters}
      />
    )

    const clearBtn = screen.getByRole('button', { name: /Clear Filters/i })
    expect(clearBtn).toBeInTheDocument()

    await userEvent.click(clearBtn)
    expect(onClearFilters).toHaveBeenCalled()
  })
})
