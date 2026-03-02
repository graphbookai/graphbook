import { useStore } from '@/store'
import { useRunData } from '@/hooks/useRunData'
import { useRunDuration } from '@/hooks/useRunDuration'
import { useIsDesktop } from '@/hooks/useMediaQuery'
import { DagGraph } from '@/components/graph/DagGraph'
import { NodeList } from '@/components/graph/NodeList'
import { PinnedPanelStack } from '@/components/layout/PinnedPanelStack'
import { RunStatusBadge } from '@/components/runs/RunStatusBadge'
import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useState } from 'react'

export function RunDetailView() {
  const selectedRunId = useStore(s => s.selectedRunId)
  const run = useRunData(selectedRunId)
  const isDesktop = useIsDesktop()
  const pinnedPanels = useStore(s => s.pinnedPanels)
  const nodeListCollapsed = useStore(s => s.nodeListCollapsed)
  const toggleNodeList = useStore(s => s.toggleNodeList)
  const [mobileTab, setMobileTab] = useState<'nodes' | 'graph'>('nodes')

  const duration = useRunDuration(run?.summary)

  if (!selectedRunId || !run) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Select a run to view details</p>
      </div>
    )
  }

  const scriptName = run.summary.script_path.split('/').pop() ?? run.summary.script_path

  return (
    <div className="flex flex-col h-full">
      {/* Run header (desktop only - mobile uses MobileNav) */}
      {isDesktop && (
        <div className="flex items-center gap-3 px-4 py-2 border-b border-border shrink-0">
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
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={toggleNodeList}
            title={nodeListCollapsed ? 'Show node list' : 'Hide node list'}
          >
            {nodeListCollapsed ? (
              <PanelRightOpen className="h-4 w-4" />
            ) : (
              <PanelRightClose className="h-4 w-4" />
            )}
          </Button>
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
          <>
            <div className="flex-1 overflow-hidden">
              <DagGraph runId={selectedRunId} />
            </div>
            {!nodeListCollapsed && (
              <div className="w-80 shrink-0 border-l border-border overflow-hidden">
                <NodeList runId={selectedRunId} />
              </div>
            )}
          </>
        ) : mobileTab === 'graph' ? (
          <DagGraph runId={selectedRunId} />
        ) : (
          <NodeList runId={selectedRunId} />
        )}
      </div>

      {/* Pinned panel stack */}
      {pinnedPanels.length > 0 && (
        <PinnedPanelStack />
      )}
    </div>
  )
}
