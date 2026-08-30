/**
 * Frontend tests for LoginPage.
 * Validates rendering, form inputs, validation error alerts, and submission states.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import LoginPage from '@/pages/LoginPage'
import { AuthContext } from '@/features/auth/AuthContext'
import type { AuthContextType } from '@/features/auth/types'

function renderLoginPage(authOverrides: Partial<AuthContextType> = {}) {
  const defaultAuthValue: AuthContextType = {
    user: null,
    session: null,
    loading: false,
    error: null,
    signIn: vi.fn().mockResolvedValue({ error: null }),
    signOut: vi.fn().mockResolvedValue(undefined),
    isAuthenticated: false,
    ...authOverrides,
  }

  return {
    ...render(
      <AuthContext.Provider value={defaultAuthValue}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </AuthContext.Provider>,
    ),
    authValue: defaultAuthValue,
  }
}

describe('LoginPage', () => {
  it('renders login form inputs and brand header', () => {
    renderLoginPage()
    expect(screen.getByText('SiteSync AI')).toBeInTheDocument()
    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeInTheDocument()
  })

  it('displays client validation error when email is omitted', async () => {
    renderLoginPage()
    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText('Please enter your email address.')).toBeInTheDocument()
    })
  })

  it('displays client validation error when password is omitted', async () => {
    renderLoginPage()
    const emailInput = screen.getByLabelText(/Email Address/i)
    fireEvent.change(emailInput, { target: { value: 'planner@sitesync.ai' } })

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText('Please enter your password.')).toBeInTheDocument()
    })
  })

  it('invokes signIn with entered credentials upon submission', async () => {
    const signInMock = vi.fn().mockResolvedValue({ error: null })
    renderLoginPage({ signIn: signInMock })

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'planner@sitesync.ai' },
    })
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'SecurePass123!' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(signInMock).toHaveBeenCalledWith('planner@sitesync.ai', 'SecurePass123!')
    })
  })

  it('displays server authentication error message when signIn fails', async () => {
    const signInMock = vi.fn().mockResolvedValue({ error: 'Invalid login credentials' })
    renderLoginPage({ signIn: signInMock })

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'wrong@sitesync.ai' },
    })
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'WrongPassword' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid login credentials')).toBeInTheDocument()
    })
  })
})
