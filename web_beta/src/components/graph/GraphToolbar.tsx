import { useReactFlow } from '@xyflow/react'
import { useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { Maximize, GitFork, ChevronsDownUp, ChevronsUpDown, ArrowDownUp, ArrowLeftRight, LayoutGrid } from 'lucide-react'

interface GraphToolbarProps {
  onResetLayout: () => void
}

export function GraphToolbar({ onResetLayout }: GraphToolbarProps) {
  const { fitView } = useReactFlow()
  const collapsedGraphNodes = useStore(s => s.collapsedGraphNodes)
  const collapseAll = useStore(s => s.collapseAllGraphNodes)
  const expandAll = useStore(s => s.expandAllGraphNodes)
  const dagDirection = useStore(s => s.dagDirection)
  const toggleDagDirection = useStore(s => s.toggleDagDirection)
  const setDesktopViewMode = useStore(s => s.setDesktopViewMode)

  const allCollapsed = collapsedGraphNodes.size > 0

  return (
    <div className="absolute top-3 right-3 flex gap-1 z-10">
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
  )
}
