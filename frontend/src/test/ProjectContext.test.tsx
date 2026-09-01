/**
 * Frontend tests for ProjectProvider & ProjectContext.
 */

import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProjectProvider } from '@/features/projects/ProjectContext'
import { useProject } from '@/features/projects/useProject'
import type { ProjectSummary } from '@/features/projects/types'

const mockProjects: ProjectSummary[] = [
  {
    projectId: 'proj-mtp-001',
    projectName: 'MTP – Refinery Expansion',
    projectCode: 'MTP-2026',
    role: 'planner',
  },
  {
    projectId: 'proj-demo-002',
    projectName: 'Downtown Medical Center',
    projectCode: 'DMC-2026',
    role: 'viewer',
  },
]

function TestConsumer() {
  const { projects, selectedProject, selectProject, currentRole } = useProject()
  return (
    <div>
      <div data-testid="project-count">{projects.length}</div>
      <div data-testid="selected-id">{selectedProject?.projectId}</div>
      <div data-testid="selected-name">{selectedProject?.projectName}</div>
      <div data-testid="selected-role">{currentRole}</div>
      <button onClick={() => selectProject('proj-demo-002')}>Select Demo</button>
    </div>
  )
}

describe('ProjectProvider', () => {
  it('initializes with default project and exposes role', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <ProjectProvider initialProjects={mockProjects} initialSelectedProjectId="proj-mtp-001">
          <TestConsumer />
        </ProjectProvider>
      </QueryClientProvider>,
    )

    expect(screen.getByTestId('project-count')).toHaveTextContent('2')
    expect(screen.getByTestId('selected-id')).toHaveTextContent('proj-mtp-001')
    expect(screen.getByTestId('selected-name')).toHaveTextContent('MTP – Refinery Expansion')
    expect(screen.getByTestId('selected-role')).toHaveTextContent('planner')
  })

  it('switches selected project when selectProject is called', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <ProjectProvider initialProjects={mockProjects} initialSelectedProjectId="proj-mtp-001">
          <TestConsumer />
        </ProjectProvider>
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByText('Select Demo'))

    expect(screen.getByTestId('selected-id')).toHaveTextContent('proj-demo-002')
    expect(screen.getByTestId('selected-name')).toHaveTextContent('Downtown Medical Center')
    expect(screen.getByTestId('selected-role')).toHaveTextContent('viewer')
  })

  it('falls back to first authorized project when stored localStorage project ID is stale/invalid', () => {
    localStorage.setItem('sitesync_selected_project_id', 'proj-unauthorized-999')
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <ProjectProvider initialProjects={mockProjects}>
          <TestConsumer />
        </ProjectProvider>
      </QueryClientProvider>,
    )

    // Falls back to proj-mtp-001
    expect(screen.getByTestId('selected-id')).toHaveTextContent('proj-mtp-001')
  })

  it('handles zero memberships cleanly with null selectedProjectId', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <ProjectProvider initialProjects={[]}>
          <TestConsumer />
        </ProjectProvider>
      </QueryClientProvider>,
    )

    expect(screen.getByTestId('project-count')).toHaveTextContent('0')
    expect(screen.getByTestId('selected-id')).toHaveTextContent('')
  })
})
