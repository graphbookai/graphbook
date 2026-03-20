import { useCallback } from 'react'
import { useReactFlow } from '@xyflow/react'
import { useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { Maximize, GitFork, ChevronsDownUp, ChevronsUpDown, ArrowDownUp, ArrowLeftRight, LayoutGrid, Pause, Play } from 'lucide-react'
import { api } from '@/lib/api'

interface GraphToolbarProps {
  onResetLayout: () => void
  runId: string
}

export function GraphToolbar({ onResetLayout, runId }: GraphToolbarProps) {
  const { fitView } = useReactFlow()
  const collapsedGraphNodes = useStore(s => s.collapsedGraphNodes)
  const collapseAll = useStore(s => s.collapseAllGraphNodes)
  const expandAll = useStore(s => s.expandAllGraphNodes)
  const dagDirection = useStore(s => s.dagDirection)
  const toggleDagDirection = useStore(s => s.toggleDagDirection)
  const setDesktopViewMode = useStore(s => s.setDesktopViewMode)
  const runState = useStore(s => s.runs.get(runId))
  const setPaused = useStore(s => s.setPaused)

  const hasPausable = runState?.graph?.has_pausable ?? false
  const isPaused = runState?.paused ?? false
  const isRunning = runState?.summary.status === 'running'

  const allCollapsed = collapsedGraphNodes.size > 0

  const togglePause = useCallback(async () => {
    if (isPaused) {
      await api.unpauseRun(runId)
      setPaused(runId, false)
    } else {
      await api.pauseRun(runId)
      setPaused(runId, true)
    }
  }, [runId, isPaused, setPaused])

  return (
    <div className="absolute top-3 right-3 flex flex-col gap-1 z-10 items-end">
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm"
          onClick={() => setDesktopViewMode('grid')}
          title="Switch to grid view"
        >
          <LayoutGrid className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm"
          onClick={allCollapsed ? expandAll : collapseAll}
          title={allCollapsed ? 'Expand all nodes' : 'Collapse all nodes'}
        >
          {allCollapsed ? (
            <ChevronsUpDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronsDownUp className="h-3.5 w-3.5" />
          )}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm"
          onClick={toggleDagDirection}
          title={dagDirection === 'TB' ? 'Switch to horizontal layout' : 'Switch to vertical layout'}
        >
          {dagDirection === 'TB' ? (
            <ArrowLeftRight className="h-3.5 w-3.5" />
          ) : (
            <ArrowDownUp className="h-3.5 w-3.5" />
          )}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm"
          onClick={() => fitView({ padding: 0.1, duration: 300 })}
          title="Fit to view"
        >
          <Maximize className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 bg-card/80 backdrop-blur-sm"
          onClick={onResetLayout}
          title="Reset layout"
        >
          <GitFork className="h-3.5 w-3.5" />
        </Button>
      </div>
      {hasPausable && isRunning && (
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="sm"
            className={`h-8 backdrop-blur-sm ${isPaused ? 'bg-yellow-500/20 border-yellow-500/50 hover:bg-yellow-500/30' : 'bg-card/80'}`}
            onClick={togglePause}
            title={isPaused ? 'Resume execution' : 'Pause execution'}
          >
            {isPaused ? (
              <>
                <Play className="h-3.5 w-3.5 mr-1" />
                <span className="text-xs">Resume</span>
              </>
            ) : (
              <>
                <Pause className="h-3.5 w-3.5 mr-1" />
                <span className="text-xs">Pause</span>
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
