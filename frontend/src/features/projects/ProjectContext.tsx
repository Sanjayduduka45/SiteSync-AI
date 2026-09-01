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
  const isAuthLoading = auth?.loading ?? false

  const { data, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiGet<AuthMeBackendResponse>('/v1/auth/me'),
    enabled: Boolean(isAuthenticated && !isAuthLoading && !initialProjects),
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
    if (initialSelectedProjectId && initialSelectedProjectId !== 'null' && initialSelectedProjectId !== 'undefined') {
      return initialSelectedProjectId
    }
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored && stored !== 'null' && stored !== 'undefined' ? stored : null
    }
    return null
  })

  // Derive effective project ID:
  // 1. If explicitSelectedProjectId is set AND is in loadedProjects, use it.
  // 2. Otherwise, if loadedProjects has elements, default to loadedProjects[0].projectId.
  // 3. Otherwise (zero memberships), effective project ID is strictly null.
  const activeProjectId = (() => {
    if (explicitSelectedProjectId && loadedProjects.some((p) => p.projectId === explicitSelectedProjectId)) {
      return explicitSelectedProjectId
    }
    return loadedProjects[0]?.projectId ?? null
  })()

  const selectProject = (projectId: string) => {
    if (!projectId || projectId === 'null' || projectId === 'undefined') {
      return
    }
    if (loadedProjects.some((p) => p.projectId === projectId)) {
      setExplicitSelectedProjectId(projectId)
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, projectId)
      }
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
