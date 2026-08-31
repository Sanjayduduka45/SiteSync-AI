/**
 * RiskDashboardPage — Primary Risk & Critical Path Intelligence Dashboard (Phase 9.6).
 * Features:
 *   - Executive Risk Summary KPI cards & category distribution
 *   - ADR-018 2D Risk & Float Exposure Heatmap Matrix
 *   - Server-side filter bar (Severity, Category, WBS, Discipline)
 *   - Tabbed view: Activity Risk Register vs Critical Path Schedule
 *   - Transitive Downstream Impact Drawer
 * Pure presentation consuming Phase 9.5 backend APIs.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProject } from '@/features/projects/useProject'
import {
  formatRiskError,
  getCriticalPath,
  getRiskActivities,
  getRiskSummary,
} from '@/features/risk/api'
import type {
  RiskCategory,
  RiskFilterParams,
  RiskSeverityLevel,
} from '@/features/risk/types'
import { CriticalPathTable } from '@/features/risk/components/CriticalPathTable'
import { DownstreamImpactDrawer } from '@/features/risk/components/DownstreamImpactDrawer'
import { RiskActivityTable } from '@/features/risk/components/RiskActivityTable'
import { RiskFilterBar } from '@/features/risk/components/RiskFilterBar'
import { RiskHeatmap } from '@/features/risk/components/RiskHeatmap'
import { RiskSummaryCards } from '@/features/risk/components/RiskSummaryCards'
import { ExportDropdown } from '@/features/exports/components/ExportDropdown'

const PAGE_SIZE = 50

type TabType = 'register' | 'cpm'

export default function RiskDashboardPage() {
  const { selectedProjectId } = useProject()

  // Tab State
  const [activeTab, setActiveTab] = useState<TabType>('register')

  // Filter State
  const [severity, setSeverity] = useState<RiskSeverityLevel | 'all'>('all')
  const [category, setCategory] = useState<RiskCategory | 'all'>('all')
  const [wbsCode, setWbsCode] = useState('')
  const [discipline, setDiscipline] = useState('')
  const [offset, setOffset] = useState(0)

  // Drawer State
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)

  // Active filters object
  const activeFilters: RiskFilterParams = {
    limit: PAGE_SIZE,
    offset,
    severity: severity !== 'all' ? severity : undefined,
    category: category !== 'all' ? category : undefined,
    wbs_code: wbsCode.trim() || undefined,
    discipline: discipline.trim() || undefined,
  }

  // 1. Risk Summary Query
  const summaryQuery = useQuery({
    queryKey: ['risk-summary', selectedProjectId],
    queryFn: () => getRiskSummary(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  // 2. Risk Activities Register Query
  const activitiesQuery = useQuery({
    queryKey: ['risk-activities', selectedProjectId, activeFilters],
    queryFn: () => getRiskActivities(selectedProjectId!, activeFilters),
    enabled: Boolean(selectedProjectId),
  })

  // 3. Critical Path Method Query
  const cpmQuery = useQuery({
    queryKey: ['critical-path', selectedProjectId],
    queryFn: () => getCriticalPath(selectedProjectId!),
    enabled: Boolean(selectedProjectId),
  })

  const handleClearFilters = () => {
    setSeverity('all')
    setCategory('all')
    setWbsCode('')
    setDiscipline('')
    setOffset(0)
  }

  const handleHeatmapCellSelect = (sev?: RiskSeverityLevel, disc?: string) => {
    if (sev) setSeverity(sev)
    if (disc) setDiscipline(disc)
    setOffset(0)
    setActiveTab('register')
  }

  const handleOpenDrawer = (activityId: string) => {
    setSelectedActivityId(activityId)
    setIsDrawerOpen(true)
  }

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false)
    setSelectedActivityId(null)
  }

  if (!selectedProjectId) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
        <p className="text-sm font-medium text-gray-900">No project selected.</p>
        <p className="text-xs text-gray-500 mt-1">
          Please select a project from the top navigation bar to view Risk and Critical Path intelligence.
        </p>
      </div>
    )
  }

  const error = summaryQuery.error || activitiesQuery.error || cpmQuery.error

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-gray-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-5 w-2 bg-blue-600 rounded-xs" />
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Risk & Critical Path Intelligence
            </h1>
          </div>
          <p className="text-sm text-gray-600 mt-1">
            Schedule network vulnerability & downstream impact assessment (Phases 9.0–9.6).
          </p>
        </div>

        {selectedProjectId && (
          <ExportDropdown
            projectId={selectedProjectId}
            dataset="risk_register"
            datasetLabel="Export Risks"
          />
        )}
      </div>

      {/* Global Error Alert */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 p-4 rounded-lg text-sm" role="alert">
          <strong>Error: </strong> {formatRiskError(error)}
        </div>
      )}

      {/* 1. Executive Summary KPI Cards */}
      <RiskSummaryCards
        summary={summaryQuery.data}
        isLoading={summaryQuery.isLoading}
      />

      {/* 2. 2D Risk & Float Exposure Heatmap Matrix */}
      <RiskHeatmap
        activities={summaryQuery.data?.items ?? []}
        isLoading={summaryQuery.isLoading}
        onSelectCell={handleHeatmapCellSelect}
      />

      {/* 3. Navigation Tabs & Views */}
      <div className="space-y-4">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-6" aria-label="Risk Dashboard Views">
            <button
              type="button"
              onClick={() => setActiveTab('register')}
              className={`py-3 px-1 border-b-2 text-sm font-semibold transition-colors ${
                activeTab === 'register'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Activity Risk Register ({summaryQuery.data?.total_activities ?? 0})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('cpm')}
              className={`py-3 px-1 border-b-2 text-sm font-semibold transition-colors ${
                activeTab === 'cpm'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Critical Path Schedule ({cpmQuery.data?.critical_activities_count ?? 0} Critical)
            </button>
          </nav>
        </div>

        {/* Tab 1: Activity Risk Register */}
        {activeTab === 'register' && (
          <div className="space-y-4">
            <RiskFilterBar
              severity={severity}
              category={category}
              wbsCode={wbsCode}
              discipline={discipline}
              onSeverityChange={(sev) => {
                setSeverity(sev)
                setOffset(0)
              }}
              onCategoryChange={(cat) => {
                setCategory(cat)
                setOffset(0)
              }}
              onWbsCodeChange={(wbs) => {
                setWbsCode(wbs)
                setOffset(0)
              }}
              onDisciplineChange={(disc) => {
                setDiscipline(disc)
                setOffset(0)
              }}
              onClearFilters={handleClearFilters}
            />

            <RiskActivityTable
              items={activitiesQuery.data?.items ?? []}
              total={activitiesQuery.data?.total ?? 0}
              limit={PAGE_SIZE}
              offset={offset}
              isLoading={activitiesQuery.isLoading}
              onPageChange={setOffset}
              onViewImpact={handleOpenDrawer}
            />
          </div>
        )}

        {/* Tab 2: Critical Path Schedule Network */}
        {activeTab === 'cpm' && (
          <CriticalPathTable
            activities={cpmQuery.data?.activities ?? []}
            totalActivities={cpmQuery.data?.total_activities ?? 0}
            criticalCount={cpmQuery.data?.critical_activities_count ?? 0}
            isLoading={cpmQuery.isLoading}
          />
        )}
      </div>

      {/* 4. Transitive Downstream Impact Drawer */}
      <DownstreamImpactDrawer
        projectId={selectedProjectId}
        activityId={selectedActivityId}
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
      />
    </div>
  )
}
