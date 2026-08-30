/**
 * Login Page — SiteSync AI Phase 2 Authentication Screen.
 *
 * Provides email + password authentication via Supabase Auth.
 * Uses existing light-theme design system and shadcn Button primitive.
 */

import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'

export default function LoginPage() {
  const { signIn, isAuthenticated, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  if (isAuthenticated && !loading) {
    return <Navigate to={from} replace />
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!email.trim()) {
      setErrorMessage('Please enter your email address.')
      return
    }

    if (!password) {
      setErrorMessage('Please enter your password.')
      return
    }

    setIsSubmitting(true)
    const result = await signIn(email.trim(), password)
    setIsSubmitting(false)

    if (result.error) {
      setErrorMessage(result.error)
    } else {
      navigate(from, { replace: true })
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white border border-gray-200 rounded-lg p-8 shadow-sm">
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <span className="h-6 w-2 bg-amber-600 rounded-sm" />
            <h1 className="text-xl font-semibold text-gray-900">SiteSync AI</h1>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Construction Project Intelligence — Sign in to continue
          </p>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md"
          >
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email-input"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Email Address
            </label>
            <input
              id="email-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="user@sitesync.ai"
            />
          </div>

          <div>
            <label
              htmlFor="password-input"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Password
            </label>
            <input
              id="password-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="••••••••"
            />
          </div>

          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 py-2 h-auto"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-gray-100 text-xs text-gray-400">
          Phase 2 Authentication Foundation — Protected by Supabase Auth & RLS.
        </div>
      </div>
    </div>
  )
}
