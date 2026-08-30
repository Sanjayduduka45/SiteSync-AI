/**
 * Authentication Provider for Supabase Auth.
 * Manages user session state, persistence, login, and logout.
 */

import { useEffect, useState, type ReactNode } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { isSupabaseConfigured, supabase } from '@/lib/supabase'
import { AuthContext } from './context'

export { AuthContext }

interface AuthProviderProps {
  children: ReactNode
  initialUser?: User | null
  initialSession?: Session | null
}

export function AuthProvider({
  children,
  initialUser = null,
  initialSession = null,
}: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(initialUser)
  const [session, setSession] = useState<Session | null>(initialSession)
  const [loading, setLoading] = useState<boolean>(() => !initialUser && isSupabaseConfigured)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isSupabaseConfigured) {
      return
    }

    let isMounted = true

    // Fetch initial session
    supabase.auth.getSession().then(({ data: { session }, error: sessionError }) => {
      if (!isMounted) return
      if (sessionError) {
        setError(sessionError.message)
      } else {
        setSession(session)
        setUser(session?.user ?? null)
      }
      setLoading(false)
    }).catch((err: unknown) => {
      if (!isMounted) return
      setError(err instanceof Error ? err.message : 'Failed to retrieve session')
      setLoading(false)
    })

    // Listen to auth state changes (login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, currentSession) => {
      if (!isMounted) return
      setSession(currentSession)
      setUser(currentSession?.user ?? null)
      setLoading(false)
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  const signIn = async (email: string, password: string): Promise<{ error: string | null }> => {
    setError(null)
    try {
      if (!isSupabaseConfigured) {
        return { error: 'Supabase credentials are not configured in frontend environment.' }
      }

      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (authError) {
        setError(authError.message)
        return { error: authError.message }
      }

      setSession(data.session)
      setUser(data.user)
      return { error: null }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sign in failed'
      setError(msg)
      return { error: msg }
    }
  }

  const signOut = async (): Promise<void> => {
    try {
      if (isSupabaseConfigured) {
        await supabase.auth.signOut()
      }
      setSession(null)
      setUser(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sign out failed')
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        error,
        signIn,
        signOut,
        isAuthenticated: Boolean(user),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
