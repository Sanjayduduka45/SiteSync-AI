/**
 * API service layer.
 * All backend communication goes through this module.
 * The base URL is read from the Vite environment variable VITE_API_URL.
 */

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
 * Perform a GET request against the backend API.
 */
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorResponse | null
    throw new Error(body?.error?.message ?? `API error: ${response.status}`)
  }

  return response.json() as Promise<T>
}
