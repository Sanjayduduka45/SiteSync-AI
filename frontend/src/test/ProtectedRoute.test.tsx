/**
 * Frontend tests for ProtectedRoute.
 * Validates route protection: redirect for unauthenticated users,
 * loading spinner during session check, and rendering children when authenticated.
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AuthContext } from '@/features/auth/AuthContext'
import type { AuthContextType } from '@/features/auth/types'

function renderWithAuth(
  initialEntries: string[],
  authOverrides: Partial<AuthContextType> = {},
) {
  const defaultAuthValue: AuthContextType = {
    user: null,
    session: null,
    loading: false,
    error: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    isAuthenticated: false,
    ...authOverrides,
  }

  return render(
    <AuthContext.Provider value={defaultAuthValue}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/login" element={<div>Login Page Screen</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Foundation Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users to /login', () => {
    renderWithAuth(['/protected'], { isAuthenticated: false, loading: false })
    expect(screen.getByText('Login Page Screen')).toBeInTheDocument()
    expect(screen.queryByText('Protected Foundation Content')).not.toBeInTheDocument()
  })

  it('shows loading spinner when authentication check is pending', () => {
    renderWithAuth(['/protected'], { loading: true, isAuthenticated: false })
    expect(screen.getByText('Verifying authentication…')).toBeInTheDocument()
    expect(screen.queryByText('Protected Foundation Content')).not.toBeInTheDocument()
  })

  it('allows access to protected child content when authenticated', () => {
    renderWithAuth(['/protected'], {
      loading: false,
      isAuthenticated: true,
      user: { id: 'user-123', email: 'planner@sitesync.ai', app_metadata: {}, user_metadata: {}, aud: 'authenticated', created_at: '' },
    })
    expect(screen.getByText('Protected Foundation Content')).toBeInTheDocument()
    expect(screen.queryByText('Login Page Screen')).not.toBeInTheDocument()
  })
})
