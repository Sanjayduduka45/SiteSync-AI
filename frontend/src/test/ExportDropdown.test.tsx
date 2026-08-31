/**
 * Tests for ExportDropdown component and export download API (Phase 10.5).
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ExportDropdown } from '@/features/exports/components/ExportDropdown'
import * as exportsApi from '@/features/exports/api'

vi.mock('@/features/exports/api')

describe('ExportDropdown', () => {
  const projectId = '00000000-0000-0000-0000-000000000001'

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(exportsApi.downloadExport).mockResolvedValue(undefined)
    vi.mocked(exportsApi.formatExportError).mockImplementation((err) =>
      err instanceof Error ? err.message : 'Export failed'
    )
  })

  it('renders export button with accessible name and toggles menu on click', async () => {
    render(
      <ExportDropdown
        projectId={projectId}
        dataset="approved_actuals"
        datasetLabel="Export Actuals"
      />
    )

    const btn = screen.getByRole('button', { name: /Export Actuals/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('menuitem', { name: /Export CSV/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Export JSON/i })).toBeInTheDocument()
  })

  it('triggers CSV download when Export CSV is clicked', async () => {
    render(
      <ExportDropdown
        projectId={projectId}
        dataset="variance"
        datasetLabel="Export Variance"
      />
    )

    const btn = screen.getByRole('button', { name: /Export Variance/i })
    await userEvent.click(btn)

    const csvItem = screen.getByRole('menuitem', { name: /Export CSV/i })
    await userEvent.click(csvItem)

    expect(exportsApi.downloadExport).toHaveBeenCalledWith(projectId, 'variance', 'csv')
  })

  it('triggers JSON download when Export JSON is clicked', async () => {
    render(
      <ExportDropdown
        projectId={projectId}
        dataset="risk_register"
        datasetLabel="Export Risks"
      />
    )

    const btn = screen.getByRole('button', { name: /Export Risks/i })
    await userEvent.click(btn)

    const jsonItem = screen.getByRole('menuitem', { name: /Export JSON/i })
    await userEvent.click(jsonItem)

    expect(exportsApi.downloadExport).toHaveBeenCalledWith(projectId, 'risk_register', 'json')
  })

  it('renders sanitized error message when export download fails', async () => {
    vi.mocked(exportsApi.downloadExport).mockRejectedValue(new Error('Network error'))
    vi.mocked(exportsApi.formatExportError).mockReturnValue('Unable to generate export. Please try again.')

    render(
      <ExportDropdown
        projectId={projectId}
        dataset="approved_actuals"
        datasetLabel="Export Actuals"
      />
    )

    const btn = screen.getByRole('button', { name: /Export Actuals/i })
    await userEvent.click(btn)

    const csvItem = screen.getByRole('menuitem', { name: /Export CSV/i })
    await userEvent.click(csvItem)

    await waitFor(() => {
      expect(screen.getByText('Unable to generate export. Please try again.')).toBeInTheDocument()
    })
  })
})
