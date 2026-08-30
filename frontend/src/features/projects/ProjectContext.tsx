/**
 * Project Context and Provider.
 * Maintains current active project selection across application features.
 */

import { useContext, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/services/api'
import { AuthContext } from '@/features/auth/context'
import { ProjectContext } from './context'
import type { ProjectContextType, ProjectSummary } from './types'

export { ProjectContext }

interface AuthMeBackendResponse {
  user: { id: string; email: string; full_name?: string }
  memberships: Array<{
    project_id: string
    project_name: string
    project_code: string
    role: 'admin' | 'planner' | 'supervisor' | 'viewer'
  }>
}

interface ProjectProviderProps {
  children: ReactNode
  initialProjects?: ProjectSummary[]
  initialSelectedProjectId?: string
}

const STORAGE_KEY = 'sitesync_selected_project_id'

export function ProjectProvider({
  children,
  initialProjects,
  initialSelectedProjectId,
}: ProjectProviderProps) {
  const auth = useContext(AuthContext)
  const isAuthenticated = auth ? auth.isAuthenticated : true

  const { data, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiGet<AuthMeBackendResponse>('/v1/auth/me'),
    enabled: Boolean(isAuthenticated && !initialProjects),
    staleTime: 60_000,
  })

  // Map memberships into ProjectSummary list
  const loadedProjects: ProjectSummary[] = initialProjects ?? (data?.memberships ?? []).map((m) => ({
    projectId: m.project_id,
    projectName: m.project_name,
    projectCode: m.project_code,
    role: m.role,
  }))

  const [explicitSelectedProjectId, setExplicitSelectedProjectId] = useState<string | null>(() => {
    if (initialSelectedProjectId) return initialSelectedProjectId
    return typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
  })

  // Derive effective project ID without setState in effect
  const activeProjectId = (() => {
    if (explicitSelectedProjectId && loadedProjects.some((p) => p.projectId === explicitSelectedProjectId)) {
      return explicitSelectedProjectId
    }
    return loadedProjects[0]?.projectId ?? null
  })()

  const selectProject = (projectId: string) => {
    setExplicitSelectedProjectId(projectId)
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, projectId)
    }
  }

  const selectedProject = loadedProjects.find((p) => p.projectId === activeProjectId) ?? null

  const value: ProjectContextType = {
    projects: loadedProjects,
    selectedProject,
    selectedProjectId: activeProjectId,
    selectProject,
    currentRole: selectedProject?.role ?? null,
    loadingProjects: isLoading,
  }

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
}
