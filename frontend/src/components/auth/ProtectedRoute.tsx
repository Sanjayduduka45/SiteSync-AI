/**
 * ProtectedRoute — Client-side route guard.
 *
 * Redirects unauthenticated users to /login while preserving intended destination.
 * Shows loading indicator during session initialization.
 *
 * Note: Server-side authorization is also enforced on all protected backend endpoints.
 */

import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/useAuth'

interface ProtectedRouteProps {
  children?: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-900 border-t-transparent" />
          <p className="text-sm text-gray-500 font-medium">Verifying authentication…</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
