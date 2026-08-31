/**
 * ExtractionResultView — Reusable component for displaying AI-extracted construction progress
 * and integrated AI Schedule Matching recommendations.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useProject } from '@/features/projects/useProject'
import { getExtractionMatches, triggerExtractionMatching } from '@/features/schedules/api'
import { MatchRecommendationsView } from '@/features/schedules/components/MatchRecommendationsView'
import type { ExtractionRecord, ExtractionResultData, ExtractedActivity } from '../types'
import { getConfidenceLevel } from '../types'

interface ExtractionResultViewProps {
  extraction: ExtractionRecord
}

export function ExtractionResultView({ extraction }: ExtractionResultViewProps) {
  const { selectedProjectId, currentRole } = useProject()
  const queryClient = useQueryClient()
  const [matchingError, setMatchingError] = useState<string | null>(null)

  const extractedData = extraction.extracted_data as ExtractionResultData | undefined
  const activities: ExtractedActivity[] = extractedData?.extracted_activities || []
  const confidence = getConfidenceLevel(extraction.confidence_score)

  const canMatch = currentRole === 'planner' || currentRole === 'admin'
  const isCompleted = extraction.status === 'completed'

  // Query matches for this extraction
  const {
    data: matchResponse,
    isLoading: isMatchesLoading,
  } = useQuery({
    queryKey: ['extraction-matches', selectedProjectId, extraction.id],
    queryFn: () => {
      if (!selectedProjectId) throw new Error('No project selected')
      return getExtractionMatches(selectedProjectId, extraction.id)
    },
    enabled: !!selectedProjectId && isCompleted,
  })

  // Mutation to trigger matching
  const matchMutation = useMutation({
    mutationFn: () => {
      if (!selectedProjectId) throw new Error('No project selected')
      return triggerExtractionMatching(selectedProjectId, extraction.id)
    },
    onSuccess: () => {
      setMatchingError(null)
      queryClient.invalidateQueries({
        queryKey: ['extraction-matches', selectedProjectId, extraction.id],
      })
    },
    onError: (err: unknown) => {
      setMatchingError(err instanceof Error ? err.message : 'Schedule matching failed')
    },
  })

  const confidenceBadgeStyles: Record<string, string> = {
    High: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    Medium: 'bg-amber-50 text-amber-800 border-amber-200',
    Low: 'bg-red-50 text-red-800 border-red-200',
  }

  const formatProgress = (activity: ExtractedActivity): string => {
    const val = activity.progress_value
    const unit = activity.progress_unit

    if (val === null || val === undefined) {
      if (unit) return `Progress unit: ${unit}`
      return 'Progress not specified'
    }

    if (unit === '%' || unit === 'percent' || unit === 'percentage') {
      return `${val}%`
    }

    if (unit) {
      return `${val} ${unit}`
    }

    return `${val}`
  }

  return (
    <div className="space-y-4">
      {/* Confidence and Model Header */}
      <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200 flex items-center justify-between">
        <div>
          <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">
            AI Extraction Confidence
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
                confidenceBadgeStyles[confidence.level] || 'bg-gray-50 text-gray-700 border-gray-200'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-current" />
              {confidence.level} · {confidence.percentage}
            </span>
          </div>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-400 font-mono block">
            {extraction.model_version}
          </span>
          <span className="text-[10px] text-gray-400 block mt-0.5">
            Status: <strong className="uppercase font-semibold text-emerald-700">{extraction.status}</strong>
          </span>
        </div>
      </div>

      {/* Extracted Activities List */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center justify-between">
          <span>Extracted Activities ({activities.length})</span>
        </h4>

        {activities.length === 0 ? (
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-500 italic text-center">
            No distinct construction activities were extracted from this note.
          </div>
        ) : (
          activities.map((activity, idx) => (
            <div
              key={idx}
              className="bg-white p-4 rounded-lg border border-gray-200 shadow-2xs space-y-3"
            >
              {/* Activity Description & Discipline Badge */}
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-bold text-gray-900 leading-snug">
                  {activity.description}
                </p>
                {activity.discipline && (
                  <span className="shrink-0 text-[10px] font-bold uppercase px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded">
                    {activity.discipline}
                  </span>
                )}
              </div>

              {/* Progress & Location Details */}
              <div className="grid grid-cols-2 gap-2 text-xs bg-gray-50 p-2.5 rounded border border-gray-100">
                <div>
                  <span className="text-[10px] text-gray-400 font-medium block">Progress</span>
                  <span className="font-semibold text-gray-800">
                    {formatProgress(activity)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-gray-400 font-medium block">Location</span>
                  <span className="font-medium text-gray-800">
                    {activity.location || 'Not specified'}
                  </span>
                </div>
                {activity.event_date && (
                  <div className="col-span-2 pt-1 border-t border-gray-200/60">
                    <span className="text-[10px] text-gray-400 font-medium block">Event Date</span>
                    <span className="font-medium text-gray-800">{activity.event_date}</span>
                  </div>
                )}
              </div>

              {/* Constraints / Blockers Alert */}
              {activity.constraints && activity.constraints.length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 block">
                    Constraints & Blockers
                  </span>
                  <div className="space-y-1">
                    {activity.constraints.map((c, cIdx) => (
                      <div
                        key={cIdx}
                        className="bg-amber-50/80 border border-amber-200 p-2 rounded text-xs text-amber-900 flex items-start gap-1.5"
                      >
                        <span className="text-amber-600 font-bold shrink-0">⚠️</span>
                        <span>{c}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verbatim Evidence Tokens */}
              <div className="space-y-1 pt-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500 block">
                  Grounding Evidence
                </span>
                {activity.evidence_tokens && activity.evidence_tokens.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {activity.evidence_tokens.map((token, tIdx) => (
                      <span
                        key={tIdx}
                        className="inline-block text-[11px] bg-gray-100 text-gray-700 px-2 py-1 rounded border border-gray-200 font-mono"
                      >
                        "{token}"
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-400 italic">No evidence tokens provided.</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Phase 6.7 & 7.5: AI Schedule Matching Results & Planner Review View */}
      {isCompleted && (
        <MatchRecommendationsView
          matches={matchResponse?.items || []}
          isLoading={isMatchesLoading}
          isMatching={matchMutation.isPending}
          canMatch={canMatch}
          onTriggerMatch={() => matchMutation.mutate()}
          matchingError={matchingError}
          projectId={selectedProjectId ?? undefined}
          extractionId={extraction.id}
          currentRole={currentRole ?? undefined}
          extractedActivities={activities}
        />
      )}
    </div>
  )
}

