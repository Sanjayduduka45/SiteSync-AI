/**
 * Authentication and authorization types for SiteSync AI frontend.
 */

import type { Session, User } from '@supabase/supabase-js'

export type ProjectRole = 'admin' | 'planner' | 'supervisor' | 'viewer'

export interface UserProfile {
  id: string
  email: string
  fullName?: string
}

export interface ProjectMembership {
  projectId: string
  projectName: string
  projectCode: string
  role: ProjectRole
}

export interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  error: string | null
  signIn: (email: string, password: string) => Promise<{ error: string | null }>
  signOut: () => Promise<void>
  isAuthenticated: boolean
}
