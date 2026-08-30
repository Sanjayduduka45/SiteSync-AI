/**
 * Status Page — Phase 1 foundation screen.
 *
 * Purpose: Verify that the frontend application bootstraps correctly and
 * can communicate with the backend health endpoint.
 *
 * This is NOT the SiteSync application dashboard.
 * It will be replaced in a future phase.
 */

import { useQuery } from '@tanstack/react-query'
import { fetchHealth, healthQueryKey } from '@/features/health/api'

export default function StatusPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: healthQueryKey,
    queryFn: fetchHealth,
    retry: 1,
  })

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white border border-gray-200 rounded-lg p-8 shadow-sm">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-900">SiteSync AI</h1>
          <p className="text-sm text-gray-500 mt-1">Phase 1 — Foundation Status</p>
        </div>

        <div className="space-y-4">
          <StatusRow label="Frontend" value="Running" status="ok" />
          <StatusRow label="React Router" value="Configured" status="ok" />
          <StatusRow label="TanStack Query" value="Configured" status="ok" />

          <div className="border-t border-gray-100 pt-4">
            {isLoading && (
              <StatusRow label="Backend API" value="Connecting…" status="pending" />
            )}
            {isError && (
              <StatusRow
                label="Backend API"
                value={error instanceof Error ? error.message : 'Unreachable'}
                status="error"
              />
            )}
            {data && (
              <>
                <StatusRow label="Backend API" value="Connected" status="ok" />
                <StatusRow label="API Status" value={data.status} status="ok" />
                <StatusRow label="Environment" value={data.environment} status="ok" />
              </>
            )}
          </div>
        </div>

        <p className="text-xs text-gray-400 mt-6">
          This screen is temporary. It exists only to verify Phase 1 connectivity.
        </p>
      </div>
    </div>
  )
}

interface StatusRowProps {
  label: string
  value: string
  status: 'ok' | 'error' | 'pending'
}

function StatusRow({ label, value, status }: StatusRowProps) {
  const indicators: Record<StatusRowProps['status'], string> = {
    ok: 'text-green-600',
    error: 'text-red-600',
    pending: 'text-yellow-600',
  }

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-600">{label}</span>
      <span className={`font-medium ${indicators[status]}`}>{value}</span>
    </div>
  )
}
