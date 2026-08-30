/**
 * AppLayout — Primary application shell for authenticated users.
 * Features:
 *  - Top navigation with brand identity
 *  - Interactive Project Selector
 *  - Active Role indicator
 *  - Navigation tabs (Status, Reports, Events)
 *  - Session identity & Sign out
 */

import { type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'
import { useProject } from '@/features/projects/useProject'

interface AppLayoutProps {
  children?: ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const { user, signOut } = useAuth()
  const { projects, selectedProjectId, selectProject, currentRole } = useProject()
  const location = useLocation()

  const navLinks = [
    { label: 'Foundation Status', path: '/' },
    { label: 'Field Reports', path: '/reports' },
    { label: 'Field Events', path: '/events' },
  ]

  const roleColors: Record<string, string> = {
    admin: 'bg-red-50 text-red-700 border-red-200',
    planner: 'bg-blue-50 text-blue-700 border-blue-200',
    supervisor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    viewer: 'bg-gray-50 text-gray-700 border-gray-200',
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left: Brand & Navigation */}
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <span className="h-6 w-2 bg-amber-600 rounded-sm" />
                <span className="text-lg font-bold text-gray-900 tracking-tight">SiteSync AI</span>
              </Link>

              {/* Project Selector */}
              <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-md px-2.5 py-1">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Project:</span>
                <select
                  aria-label="Select Project"
                  value={selectedProjectId || ''}
                  onChange={(e) => selectProject(e.target.value)}
                  className="bg-transparent text-sm font-medium text-gray-900 focus:outline-none cursor-pointer pr-2"
                >
                  {projects.map((p) => (
                    <option key={p.projectId} value={p.projectId}>
                      {p.projectName} ({p.projectCode})
                    </option>
                  ))}
                  {projects.length === 0 && <option value="">No projects assigned</option>}
                </select>

                {currentRole && (
                  <span
                    className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                      roleColors[currentRole] || 'bg-gray-50 text-gray-600'
                    }`}
                  >
                    {currentRole}
                  </span>
                )}
              </div>

              {/* Navigation Links */}
              <nav className="hidden md:flex items-center gap-1">
                {navLinks.map((link) => {
                  const isActive =
                    link.path === '/'
                      ? location.pathname === '/'
                      : location.pathname.startsWith(link.path)

                  return (
                    <Link
                      key={link.path}
                      to={link.path}
                      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-gray-100 text-gray-900 font-semibold'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`}
                    >
                      {link.label}
                    </Link>
                  )
                })}
              </nav>
            </div>

            {/* Right: User & Actions */}
            <div className="flex items-center gap-3">
              {user && (
                <div className="hidden sm:flex flex-col text-right">
                  <span className="text-xs font-medium text-gray-900">{user.email}</span>
                  <span className="text-[10px] text-gray-400">Authenticated</span>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => signOut()}
                className="text-xs text-gray-700 hover:bg-gray-100"
              >
                Sign out
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation bar */}
        <div className="md:hidden border-t border-gray-100 px-4 py-2 flex items-center gap-2 overflow-x-auto">
          {navLinks.map((link) => {
            const isActive =
              link.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(link.path)

            return (
              <Link
                key={link.path}
                to={link.path}
                className={`px-2.5 py-1 rounded text-xs font-medium whitespace-nowrap ${
                  isActive ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {link.label}
              </Link>
            )
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  )
}
