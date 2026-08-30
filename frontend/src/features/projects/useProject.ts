import { useContext } from 'react'
import { ProjectContext } from './context'
import type { ProjectContextType } from './types'

export function useProject(): ProjectContextType {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider')
  }
  return context
}
