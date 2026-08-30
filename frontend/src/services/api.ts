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
 * Perform a PATCH request against the backend API.
 */
export async function apiPatch<T>(path: string, payload: unknown): Promise<T> {
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
