import { useStore } from '@/store'
import { useRunData } from '@/hooks/useRunData'
import { useRunDuration } from '@/hooks/useRunDuration'
import { useIsDesktop } from '@/hooks/useMediaQuery'
import { useComparisonContext } from '@/hooks/useComparisonContext'
import { DagGraph } from '@/components/graph/DagGraph'
import { NodeList } from '@/components/graph/NodeList'
import { NodeGridView } from '@/components/graph/NodeGridView'
import { PinnedPanelStack } from '@/components/layout/PinnedPanelStack'
import { TimelineScrubber } from '@/components/timeline/TimelineScrubber'
import { RunStatusBadge } from '@/components/runs/RunStatusBadge'
import { useState } from 'react'

export function RunDetailView() {
  const selectedRunId = useStore(s => s.selectedRunId)
  const { isComparison, runIds: comparisonRunIds } = useComparisonContext()

  // For comparison groups, use the first run's data for the graph view
  const effectiveRunId = isComparison ? comparisonRunIds[0] ?? selectedRunId : selectedRunId
  const run = useRunData(effectiveRunId)
  const isDesktop = useIsDesktop()
  const pinnedPanels = useStore(s => s.pinnedPanels)
  const desktopViewMode = useStore(s => s.desktopViewMode)
  const runColors = useStore(s => s.runColors)
  const runNames = useStore(s => s.runNames)
  const runs = useStore(s => s.runs)
  const [mobileTab, setMobileTab] = useState<'nodes' | 'graph'>('nodes')

  const duration = useRunDuration(run?.summary)

  if (!selectedRunId || !run) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Select a run to view details</p>
      </div>
    )
  }

  const scriptName = isComparison
    ? `Comparing ${comparisonRunIds.length} runs`
    : (run.summary.script_path.split('/').pop() ?? run.summary.script_path)

  return (
    <div className="flex flex-col h-full">
      {/* Run header (desktop only - mobile uses MobileNav) */}
      {isDesktop && (
        <div className="border-b border-border shrink-0">
          <div className="flex items-center gap-3 px-4 py-2">
            <span className="text-sm font-medium">{scriptName}</span>
            <RunStatusBadge status={run.summary.status} />
            <span className="text-xs text-muted-foreground">{duration}</span>
            <span className="text-xs text-muted-foreground">
              {run.summary.node_count} node{run.summary.node_count !== 1 ? 's' : ''}
            </span>
            {run.graph?.workflow_description && (
              <span className="text-xs text-muted-foreground truncate max-w-xs" title={run.graph.workflow_description}>
                {run.graph.workflow_description.split('\n')[0].replace(/^#\s*/, '')}
              </span>
            )}
          </div>
          {/* Comparison banner */}
          {isComparison && comparisonRunIds.length > 0 && (() => {
            const names = comparisonRunIds.map(rid => {
              const r = runs.get(rid)
              return runNames.get(rid) || r?.summary.script_path.split('/').pop() || rid
            })
            const fullText = `Showing graph of ${names[0]}, and comparing it with ${names.slice(1).join(', ')}`
            return (
              <div
                className="truncate whitespace-nowrap px-4 py-1.5 border-t border-border bg-muted/30 text-xs"
                title={fullText}
              >
                <span className="text-muted-foreground">Showing graph of </span>
                {comparisonRunIds.map((rid, i) => {
                  const color = runColors.get(rid) ?? '#60a5fa'
                  return (
                    <span key={rid} className="inline-flex items-center gap-1">
                      {i === 1 && <span className="text-muted-foreground">, and comparing it with </span>}
                      {i > 1 && <span className="text-muted-foreground">, </span>}
                      <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ backgroundColor: color }} />
                      <span className="font-medium text-foreground">{names[i]}</span>
                    </span>
                  )
                })}
              </div>
            )
          })()}
        </div>
      )}

      {/* Mobile tab bar */}
      {!isDesktop && (
        <div className="flex border-b border-border shrink-0">
          <button
            className={`flex-1 py-2 text-sm font-medium text-center transition-colors ${mobileTab === 'nodes' ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground'}`}
            onClick={() => setMobileTab('nodes')}
          >
            Nodes
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium text-center transition-colors ${mobileTab === 'graph' ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground'}`}
            onClick={() => setMobileTab('graph')}
          >
            Graph
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 overflow-hidden flex">
        {isDesktop ? (
          desktopViewMode === 'grid' ? (
            <div className="flex-1 overflow-hidden">
              <NodeGridView runId={effectiveRunId!} />
            </div>
          ) : (
            <div className="flex-1 overflow-hidden">
              <DagGraph runId={effectiveRunId!} />
            </div>
          )
        ) : mobileTab === 'graph' ? (
          <DagGraph runId={effectiveRunId!} />
        ) : (
          <NodeList runId={effectiveRunId!} />
        )}
      </div>

      {/* Timeline scrubber */}
      <TimelineScrubber runId={effectiveRunId!} />

      {/* Pinned panel stack */}
      {pinnedPanels.length > 0 && (
        <PinnedPanelStack />
      )}
    </div>
  )
}
