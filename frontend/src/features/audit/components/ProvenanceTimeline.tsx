import type { ProvenanceChain } from '../types'

interface ProvenanceTimelineProps {
  chain: ProvenanceChain
}

const NODE_TYPE_LABELS: Record<string, { label: string; bg: string; text: string; border: string }> = {
  FIELD_INPUT: {
    label: 'Field Input',
    bg: 'bg-sky-50',
    text: 'text-sky-700',
    border: 'border-sky-200',
  },
  AI_EXTRACTION: {
    label: 'AI Extraction',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    border: 'border-indigo-200',
  },
  AI_MATCH: {
    label: 'Match Recommendation',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    border: 'border-purple-200',
  },
  PLANNER_DECISION: {
    label: 'Planner Decision',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  APPROVED_ACTUAL: {
    label: 'Approved Actual',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
  VARIANCE: {
    label: 'Plan vs Actual Variance',
    bg: 'bg-teal-50',
    text: 'text-teal-700',
    border: 'border-teal-200',
  },
  RISK: {
    label: 'Schedule Risk Assessment',
    bg: 'bg-rose-50',
    text: 'text-rose-700',
    border: 'border-rose-200',
  },
}

export function ProvenanceTimeline({ chain }: ProvenanceTimelineProps) {
  const { nodes, unresolved_links, is_complete } = chain

  return (
    <div className="flex flex-col gap-6">
      {/* Incomplete Lineage Warning */}
      {!is_complete && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-xs flex flex-col gap-1.5" role="alert">
          <div className="flex items-center gap-2 font-semibold">
            <span className="w-2 h-2 rounded-full bg-amber-500" aria-hidden="true" />
            Provenance chain is incomplete.
          </div>
          {unresolved_links && unresolved_links.length > 0 && (
            <ul className="list-disc list-inside space-y-0.5 text-amber-700 pl-1">
              {unresolved_links.map((link, idx) => (
                <li key={idx}>{link}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Nodes Timeline */}
      <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
        {nodes.map((node) => {
          const config = NODE_TYPE_LABELS[node.node_type] || {
            label: node.node_type,
            bg: 'bg-gray-50',
            text: 'text-gray-700',
            border: 'border-gray-200',
          }

          const formattedTime = node.timestamp
            ? new Date(node.timestamp).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : null

          return (
            <div key={node.node_id} className="relative group">
              {/* Timeline Marker Dot */}
              <div
                className="absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-white bg-gray-400 group-hover:bg-amber-600 transition-colors shadow-sm"
                aria-hidden="true"
              />

              {/* Node Card */}
              <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex flex-col gap-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider w-fit border ${config.bg} ${config.text} ${config.border}`}
                    >
                      {config.label}
                    </span>
                    <h4 className="text-sm font-semibold text-gray-900 mt-1">{node.title}</h4>
                  </div>
                  {formattedTime && (
                    <span className="text-[11px] text-gray-400 font-mono whitespace-nowrap">
                      {formattedTime}
                    </span>
                  )}
                </div>

                {/* Node Status / Metadata */}
                {node.status && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 font-medium">Status:</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-800">
                      {node.status}
                    </span>
                  </div>
                )}

                {/* Key Details Inspection */}
                {node.details && Object.keys(node.details).length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-2.5 text-xs text-gray-700 space-y-1">
                    {Object.entries(node.details).map(([key, val]) => {
                      if (val === null || val === undefined || typeof val === 'object') {
                        return null
                      }
                      return (
                        <div key={key} className="flex justify-between items-center text-[11px]">
                          <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                          <span className="font-mono text-gray-900 font-medium">{String(val)}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
