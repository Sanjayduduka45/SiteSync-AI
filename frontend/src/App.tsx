/**
 * Application bootstrap.
 * - Wraps the entire app in TanStack Query's QueryClientProvider, AuthProvider, and ProjectProvider.
 * - Sets up React Router with public /login route and protected application routes.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '@/features/auth/AuthContext'
import { ProjectProvider } from '@/features/projects/ProjectContext'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AppLayout } from '@/components/layout/AppLayout'
import LoginPage from '@/pages/LoginPage'
import StatusPage from '@/pages/StatusPage'
import ReportsPage from '@/pages/ReportsPage'
import EventsPage from '@/pages/EventsPage'
import FieldInputsPage from '@/pages/FieldInputsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ProjectProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <StatusPage />
                    </AppLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/reports"
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <ReportsPage />
                    </AppLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/events"
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <EventsPage />
                    </AppLayout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/inputs"
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <FieldInputsPage />
                    </AppLayout>
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </ProjectProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}
