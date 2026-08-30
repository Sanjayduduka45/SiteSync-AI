/**
 * Application bootstrap.
 * - Wraps the entire app in TanStack Query's QueryClientProvider.
 * - Sets up React Router.
 * - Defines top-level routes.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import StatusPage from '@/pages/StatusPage'

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
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<StatusPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
