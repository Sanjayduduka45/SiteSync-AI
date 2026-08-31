/**
 * Tests for RiskSummaryCards component — SiteSync AI Phase 9.6.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { RiskSummaryCards } from '@/features/risk/components/RiskSummaryCards'
import type { ProjectRiskSummary } from '@/features/risk/types'

describe('RiskSummaryCards', () => {
  const mockSummary: ProjectRiskSummary = {
    project_id: '00000000-0000-0000-0000-000000000001',
    total_activities: 25,
    critical_severity_count: 5,
    high_severity_count: 8,
    medium_severity_count: 7,
    low_severity_count: 2,
    critical_path_delay_count: 3,
    float_erosion_count: 6,
    downstream_bottleneck_count: 4,
    predecessor_blocker_count: 9,
    unquantified_milestone_lag_count: 1,
    unit_mismatch_exposure_count: 11,
    average_risk_score: 54.2,
    items: [],
  }

  it('renders all factual KPI values directly from backend summary', () => {
    render(<RiskSummaryCards summary={mockSummary} />)

    expect(screen.getByText('25')).toBeInTheDocument() // Total Activities
    expect(screen.getByText('5')).toBeInTheDocument() // Critical Risk
    expect(screen.getByText('8')).toBeInTheDocument() // High Risk
    expect(screen.getByText('7')).toBeInTheDocument() // Medium Risk
    expect(screen.getByText('2')).toBeInTheDocument() // Low Risk
    expect(screen.getByText('54.2')).toBeInTheDocument() // Average Risk Score
  })



  it('renders all canonical category distribution counts accurately', () => {
    render(<RiskSummaryCards summary={mockSummary} />)

    expect(screen.getByText('Critical Path Delay:')).toBeInTheDocument()
    expect(screen.getByText('Float Erosion:')).toBeInTheDocument()
    expect(screen.getByText('Downstream Bottleneck:')).toBeInTheDocument()
    expect(screen.getByText('Predecessor Blocker:')).toBeInTheDocument()
    expect(screen.getByText('Milestone Lag:')).toBeInTheDocument()
    expect(screen.getByText('Unit Mismatch Exposure:')).toBeInTheDocument()

    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('renders loading skeleton when isLoading is true', () => {
    render(<RiskSummaryCards isLoading={true} />)
    expect(screen.getByTestId('risk-summary-loading')).toBeInTheDocument()
  })

  it('renders empty message when summary data is undefined', () => {
    render(<RiskSummaryCards summary={undefined} />)
    expect(screen.getByText('No risk summary data available.')).toBeInTheDocument()
  })
})
