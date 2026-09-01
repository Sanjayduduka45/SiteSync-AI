/**
 * API service layer.
 * All backend communication goes through this module.
 * The base URL is read from the Vite environment variable VITE_API_URL.
 * Automatically attaches Supabase Auth Bearer JWT tokens to authenticated requests.
 */

import { isSupabaseConfigured, supabase } from '@/lib/supabase'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface ApiErrorResponse {
  error: ApiError
}

/**
 * Validates request paths to prevent malformed project-scoped API requests.
 */
function validatePath(path: string): void {
  if (
    path.includes('/projects/null') ||
    path.includes('/projects/undefined') ||
    path.includes('/projects//')
  ) {
    throw new Error('No project is selected.')
  }
}

/**
 * Retrieve authorization header containing the active Supabase JWT token.
 */
export async function getAuthHeader(): Promise<Record<string, string>> {
  if (!isSupabaseConfigured) return {}
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession()
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` }
    }
  } catch {
    // Fail safe if session retrieval is interrupted
  }
  return {}
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null
    throw new Error(body?.error?.message ?? `API error: ${response.status}`)
  }
  return response.json() as Promise<T>
}

/**
 * Perform a GET request against the backend API with optional authentication.
 */
export async function apiGet<T>(path: string): Promise<T> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
    },
  })
  return handleResponse<T>(response)
}

/**
 * Perform a POST request against the backend API.
 */
export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<T>(response)
}

/**
 * Perform a multipart/form-data POST request against the backend API (for file uploads).
 */
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      ...authHeader,
    },
    body: formData,
  })
  return handleResponse<T>(response)
}

/**
 * Perform a PATCH request against the backend API.
 */
export async function apiPatch<T>(path: string, payload: unknown): Promise<T> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<T>(response)
}

/**
 * Perform a DELETE request against the backend API.
 */
export async function apiDelete<T>(path: string): Promise<T> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
    },
  })
  return handleResponse<T>(response)
}

/**
 * Perform an authenticated GET request against the backend API to download a binary/blob payload.
 */
export async function apiDownload(path: string): Promise<{ blob: Blob; filename?: string }> {
  validatePath(path)
  const authHeader = await getAuthHeader()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      ...authHeader,
    },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null
    throw new Error(body?.error?.message ?? `API error: ${response.status}`)
  }
  const contentDisposition = response.headers.get('Content-Disposition')
  let filename: string | undefined
  if (contentDisposition) {
    const match = /filename=["']?([^"';]+)["']?/i.exec(contentDisposition)
    if (match && match[1]) {
      filename = match[1]
    }
  }
  const blob = await response.blob()
  return { blob, filename }
}
