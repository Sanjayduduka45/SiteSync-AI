/**
 * Phase 1 foundation test — StatusPage renders without errors.
 * Validates that React, TanStack Query, and React Router are correctly wired.
 */

import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import StatusPage from '@/pages/StatusPage'

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StatusPage', () => {
  it('renders the SiteSync AI title', () => {
    renderWithProviders(<StatusPage />)
    expect(screen.getByText('SiteSync AI')).toBeInTheDocument()
  })

  it('renders the phase label', () => {
    renderWithProviders(<StatusPage />)
    const matches = screen.getAllByText(/Phase 1/i)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('shows frontend running status', () => {
    renderWithProviders(<StatusPage />)
    expect(screen.getByText('Frontend')).toBeInTheDocument()
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('shows connecting state while backend call is pending', () => {
    renderWithProviders(<StatusPage />)
    expect(screen.getByText('Connecting…')).toBeInTheDocument()
  })
})
