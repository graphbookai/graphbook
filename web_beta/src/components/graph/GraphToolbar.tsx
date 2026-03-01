import { useReactFlow } from '@xyflow/react'
import { useStore } from '@/store'
import { Button } from '@/components/ui/button'
import { Maximize, RotateCcw } from 'lucide-react'

interface GraphToolbarProps {
  runId: string
}

export function GraphToolbar({ runId }: GraphToolbarProps) {
  const { fitView } = useReactFlow()
  const resetLayout = useStore(s => s.resetLayout)

  return (
    <div className="absolute top-3 right-3 flex gap-1 z-10">
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
        onClick={() => resetLayout(runId)}
        title="Reset layout"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}
