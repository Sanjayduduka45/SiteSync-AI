/**
 * Supabase client configuration for SiteSync AI.
 *
 * Security rules:
 * - Uses ONLY client-safe anonymous key (VITE_SUPABASE_ANON_KEY).
 * - NEVER imports or references service role keys.
 * - Handles missing/placeholder env vars gracefully with safe fallback.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

function isValidHttpUrl(str: string): boolean {
  if (!str || str.includes('placeholder') || str.includes('PASTE_YOUR_')) {
    return false
  }
  try {
    const url = new URL(str)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export const isSupabaseConfigured = Boolean(
  supabaseUrl &&
  supabaseAnonKey &&
  isValidHttpUrl(supabaseUrl) &&
  !supabaseAnonKey.includes('placeholder') &&
  !supabaseAnonKey.includes('PASTE_YOUR_') &&
  supabaseUrl !== 'your_supabase_project_url_here' &&
  supabaseAnonKey !== 'your_supabase_anon_key_here'
)

// Initialize client if valid URL is present; otherwise create dummy client for offline/mock test resilience
export const supabase: SupabaseClient = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : createClient('https://placeholder.supabase.co', 'placeholder-anon-key', {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
      },
    })
