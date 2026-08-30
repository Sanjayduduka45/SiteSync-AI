import type { ProjectRole } from '@/features/auth/types'

export interface ProjectSummary {
  projectId: string
  projectName: string
  projectCode: string
  role: ProjectRole
}

export interface ProjectContextType {
  projects: ProjectSummary[]
  selectedProject: ProjectSummary | null
  selectedProjectId: string | null
  selectProject: (projectId: string) => void
  currentRole: ProjectRole | null
  loadingProjects: boolean
}
