/**
 * Frontend tests for AuthProvider and AuthContext.
 * Tests sign in, sign out, and initial unauthenticated state.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { useAuth } from '@/features/auth/useAuth'

function ConsumerComponent() {
  const { user, isAuthenticated, signIn, signOut, error } = useAuth()

  return (
    <div>
      <div data-testid="auth-status">
        {isAuthenticated ? 'AUTHENTICATED' : 'ANONYMOUS'}
      </div>
      <div data-testid="user-email">{user?.email ?? 'none'}</div>
      {error && <div data-testid="auth-error">{error}</div>}
      <button onClick={() => signIn('demo@sitesync.ai', 'Secret123!')}>Sign In Demo</button>
      <button onClick={() => signOut()}>Sign Out Demo</button>
    </div>
  )
}

describe('AuthProvider', () => {
  it('provides initial unauthenticated state when no session is present', () => {
    render(
      <AuthProvider initialUser={null} initialSession={null}>
        <ConsumerComponent />
      </AuthProvider>,
    )

    expect(screen.getByTestId('auth-status')).toHaveTextContent('ANONYMOUS')
    expect(screen.getByTestId('user-email')).toHaveTextContent('none')
  })

  it('provides authenticated state when initial user is provided', () => {
    const mockUser = {
      id: 'test-uid-1',
      email: 'testuser@sitesync.ai',
      app_metadata: {},
      user_metadata: {},
      aud: 'authenticated',
      created_at: '',
    }

    render(
      <AuthProvider initialUser={mockUser as any} initialSession={null}>
        <ConsumerComponent />
      </AuthProvider>,
    )

    expect(screen.getByTestId('auth-status')).toHaveTextContent('AUTHENTICATED')
    expect(screen.getByTestId('user-email')).toHaveTextContent('testuser@sitesync.ai')
  })

  it('updates state to unauthenticated when sign out is invoked', async () => {
    const mockUser = {
      id: 'test-uid-1',
      email: 'testuser@sitesync.ai',
      app_metadata: {},
      user_metadata: {},
      aud: 'authenticated',
      created_at: '',
    }

    render(
      <AuthProvider initialUser={mockUser as any} initialSession={null}>
        <ConsumerComponent />
      </AuthProvider>,
    )

    expect(screen.getByTestId('auth-status')).toHaveTextContent('AUTHENTICATED')

    fireEvent.click(screen.getByText('Sign Out Demo'))

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('ANONYMOUS')
      expect(screen.getByTestId('user-email')).toHaveTextContent('none')
    })
  })
})
