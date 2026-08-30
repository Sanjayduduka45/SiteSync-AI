import { createContext } from 'react'
import type { ProjectContextType } from './types'

export const ProjectContext = createContext<ProjectContextType | undefined>(undefined)
