/**
 * MatchRecommendationsView — Visualizes AI Schedule Matching recommendations.
 * Renders recommended baseline activities, explainable scoring breakdowns,
 * alternative candidates, extracted context, and human decision controls.
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { MatchDecisionControls } from '@/features/decisions/components/MatchDecisionControls'
import type { ExtractedActivity } from '@/features/extractions/types'
import type { MatchRecommendation } from '../types'
import { getMatchConfidenceBand } from '../types'

interface MatchRecommendationsViewProps {
  matches: MatchRecommendation[]
  isLoading: boolean
  isMatching: boolean
  canMatch: boolean
  onTriggerMatch: () => void
  matchingError?: string | null
  projectId?: string
  extractionId?: string
  currentRole?: string
  extractedActivities?: ExtractedActivity[]
}

export function MatchRecommendationsView({
  matches,
  isLoading,
  isMatching,
  canMatch,
  onTriggerMatch,
  matchingError,
  projectId,
  extractionId,
  currentRole,
  extractedActivities,
}: MatchRecommendationsViewProps) {
  const [expandedBreakdown, setExpandedBreakdown] = useState<Record<number, boolean>>({})

  const toggleBreakdown = (index: number) => {
    setExpandedBreakdown((prev) => ({
      ...prev,
      [index]: !prev[index],
    }))
  }

  const confidenceBadgeStyles: Record<string, string> = {
    HIGH: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    MEDIUM: 'bg-amber-50 text-amber-800 border-amber-200',
    LOW: 'bg-red-50 text-red-800 border-red-200',
  }

  return (
    <div className="space-y-4 pt-3 border-t border-gray-200">
      {/* Section Header with Action */}
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-gray-900 flex items-center gap-1.5">
            <span>🎯</span> Schedule Alignment
          </h4>
          <p className="text-[11px] text-gray-500">
            Multi-factor candidate matching against project baseline
          </p>
        </div>

        {canMatch && matches.length > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={onTriggerMatch}
            disabled={isMatching}
            className="text-xs h-7 px-2.5 bg-white text-gray-900 border-gray-300 hover:bg-gray-50 font-medium"
          >
            {isMatching ? 'Matching…' : 'Re-match to Schedule'}
          </Button>
        )}
      </div>

      {/* Matching Error */}
      {matchingError && (
        <div className="bg-red-50 border border-red-200 p-3 rounded-lg text-xs text-red-700">
          <p className="font-semibold">Schedule matching error</p>
          <p className="mt-0.5">{matchingError}</p>
        </div>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="p-6 bg-gray-50 rounded-lg border border-gray-200 text-center">
          <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-900 border-t-transparent mb-2" />
          <p className="text-xs text-gray-500">Retrieving schedule matches…</p>
        </div>
      ) : isMatching ? (
        <div className="p-6 bg-blue-50/60 rounded-lg border border-blue-200 text-center space-y-2">
          <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-blue-700 border-t-transparent" />
          <p className="text-xs font-semibold text-blue-900">Matching to schedule activities…</p>
          <p className="text-[11px] text-blue-700">
            Generating embeddings, performing vector search, and calculating contextual scores.
          </p>
        </div>
      ) : matches.length === 0 ? (
        <div className="p-6 bg-gray-50 rounded-lg border border-gray-200 text-center space-y-2">
          <p className="text-xs text-gray-500">
            No schedule matches yet. Run Match to Schedule to generate recommendations.
          </p>
          {canMatch ? (
            <Button
              size="sm"
              onClick={onTriggerMatch}
              disabled={isMatching}
              className="bg-gray-900 text-white hover:bg-gray-800 text-xs"
            >
              Match to Schedule
            </Button>
          ) : (
            <p className="text-[11px] text-gray-400 italic">
              Schedule matching can be triggered by planners and administrators.
            </p>
          )}
        </div>
      ) : (
        /* Match Recommendations List */
        <div className="space-y-4">
          {matches.map((rec) => {
            const band = getMatchConfidenceBand(rec.confidence_score)
            const showBreakdown = expandedBreakdown[rec.activity_index] ?? false
            const bd = rec.scoring_breakdown
            const actContext = extractedActivities?.[rec.activity_index]

            return (
              <div
                key={rec.id}
                className="bg-white p-4 rounded-lg border border-gray-200 shadow-2xs space-y-3.5"
                data-testid={`match-card-${rec.activity_index}`}
              >
                {/* 1, 2, 3: Header: Recommended Match & Confidence */}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
                      Recommended Match (Activity #{rec.activity_index + 1})
                    </span>
                    <h5 className="text-xs font-bold text-gray-900 mt-0.5">
                      <span className="font-mono text-gray-600 mr-1.5">
                        {rec.recommended_activity_code || 'ACT'}
                      </span>
                      {rec.recommended_activity_name || 'Schedule Activity'}
                    </h5>
                  </div>

                  <span
                    className={`shrink-0 inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border ${
                      confidenceBadgeStyles[band.level] || 'bg-gray-50 text-gray-700'
                    }`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                    {band.level} · {band.percentage}
                  </span>
                </div>

                {/* 6, 7, 8, 9, 10: Extracted Activity Grounding Context */}
                {actContext && (
                  <div className="bg-gray-50/80 rounded-lg p-2.5 border border-gray-200/80 space-y-2 text-xs">
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      <div>
                        <span className="text-[10px] text-gray-400 font-medium block">Extracted Quantity</span>
                        <span className="font-semibold text-gray-800">
                          {actContext.progress_value !== null && actContext.progress_value !== undefined
                            ? `${actContext.progress_value} ${actContext.progress_unit || ''}`
                            : 'Not specified'}
                        </span>
                      </div>

                      <div>
                        <span className="text-[10px] text-gray-400 font-medium block">Event Date</span>
                        <span className="font-medium text-gray-800">
                          {actContext.event_date || 'Not specified'}
                        </span>
                      </div>

                      <div className="col-span-2 sm:col-span-1">
                        <span className="text-[10px] text-gray-400 font-medium block">Location</span>
                        <span className="font-medium text-gray-800 truncate block">
                          {actContext.location || 'Not specified'}
                        </span>
                      </div>
                    </div>

                    {/* Evidence Tokens */}
                    {actContext.evidence_tokens && actContext.evidence_tokens.length > 0 && (
                      <div className="pt-1.5 border-t border-gray-200/60 flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] font-bold text-gray-400 uppercase">Evidence:</span>
                        {actContext.evidence_tokens.map((token, tIdx) => (
                          <span
                            key={tIdx}
                            className="inline-block text-[10px] bg-white text-gray-700 px-1.5 py-0.5 rounded border border-gray-200 font-mono"
                          >
                            "{token}"
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* 4: Explainable Scoring Breakdown Toggle & Details */}
                <div className="bg-gray-50 rounded-lg border border-gray-200 p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-gray-700">Why this match?</span>
                    <button
                      type="button"
                      onClick={() => toggleBreakdown(rec.activity_index)}
                      className="text-[11px] text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                    >
                      {showBreakdown ? 'Hide Breakdown ▲' : 'View Scoring Breakdown ▼'}
                    </button>
                  </div>

                  {showBreakdown && (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-gray-200/80 text-[11px]">
                      <div className="p-2 bg-white rounded border border-gray-200">
                        <span className="text-[10px] text-gray-400 font-medium block">
                          Semantic Similarity (70%)
                        </span>
                        <span className="font-bold text-gray-900">
                          {Math.round(bd.semantic_similarity * 100)}%
                        </span>
                      </div>

                      <div className="p-2 bg-white rounded border border-gray-200">
                        <span className="text-[10px] text-gray-400 font-medium block">
                          Discipline Alignment (15%)
                        </span>
                        <span className="font-bold text-gray-900">
                          {Math.round((bd.discipline_contribution / 0.15) * 100)}%
                        </span>
                      </div>

                      <div className="p-2 bg-white rounded border border-gray-200">
                        <span className="text-[10px] text-gray-400 font-medium block">
                          Location Alignment (10%)
                        </span>
                        <span className="font-bold text-gray-900">
                          {Math.round((bd.location_contribution / 0.10) * 100)}%
                        </span>
                      </div>

                      <div className="p-2 bg-white rounded border border-gray-200">
                        <span className="text-[10px] text-gray-400 font-medium block">
                          Temporal Alignment (5%)
                        </span>
                        <span className="font-bold text-gray-900">
                          {Math.round((bd.temporal_contribution / 0.05) * 100)}%
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* 5: Alternative Candidates */}
                {rec.alternative_matches && rec.alternative_matches.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500 block">
                      Alternative Candidates ({rec.alternative_matches.length})
                    </span>
                    <div className="space-y-1.5">
                      {rec.alternative_matches.map((alt) => {
                        const altBand = getMatchConfidenceBand(alt.confidence_score)
                        return (
                          <div
                            key={alt.schedule_activity_id}
                            className="flex items-center justify-between p-2 rounded bg-gray-50/70 border border-gray-200 text-xs"
                          >
                            <div className="truncate pr-2">
                              <span className="font-mono text-[11px] text-gray-500 mr-1.5">
                                {alt.activity_code || 'ACT'}
                              </span>
                              <span className="font-medium text-gray-800 truncate">
                                {alt.activity_name || 'Alternative Activity'}
                              </span>
                              {alt.discipline && (
                                <span className="ml-2 text-[10px] text-gray-500">
                                  ({alt.discipline})
                                </span>
                              )}
                            </div>
                            <span className="shrink-0 text-[11px] font-semibold text-gray-600 bg-white px-2 py-0.5 rounded border border-gray-200">
                              {altBand.percentage}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Phase 7.5: Human Planner Decision Controls & Status */}
                {projectId && extractionId && (
                  <MatchDecisionControls
                    projectId={projectId}
                    extractionId={extractionId}
                    match={rec}
                    currentRole={currentRole}
                    extractedActivity={actContext}
                  />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
