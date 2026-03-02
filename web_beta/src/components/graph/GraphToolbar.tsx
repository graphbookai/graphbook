import { useReactFlow } from '@xyflow/react'
import { useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { Maximize, RotateCcw, ChevronsDownUp, ChevronsUpDown } from 'lucide-react'

interface GraphToolbarProps {
  onResetLayout: () => void
}

export function GraphToolbar({ onResetLayout }: GraphToolbarProps) {
  const { fitView } = useReactFlow()
  const collapsedGraphNodes = useStore(s => s.collapsedGraphNodes)
  const collapseAll = useStore(s => s.collapseAllGraphNodes)
  const expandAll = useStore(s => s.expandAllGraphNodes)

  const allCollapsed = collapsedGraphNodes.size > 0

  return (
    <div className="absolute top-3 right-3 flex gap-1 z-10">
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
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}
