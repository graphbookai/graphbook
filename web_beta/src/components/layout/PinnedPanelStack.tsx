import { useStore } from '@/store'
import { useComparisonContext } from '@/hooks/useComparisonContext'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { NodeTabContent } from '@/components/node-tabs/NodeTabContent'

export function PinnedPanelStack() {
  const pinnedPanels = useStore(s => s.pinnedPanels)
  const unpinPanel = useStore(s => s.unpinPanel)
  const { isComparison, runIds } = useComparisonContext()

  if (pinnedPanels.length === 0) return null

  return (
    <div className="border-t border-border bg-card shrink-0">
      <div className="flex gap-2 p-2 overflow-x-auto">
        {pinnedPanels.map(panel => (
          <div key={panel.id} className="min-w-[300px] max-w-[400px] border border-border rounded-md bg-card flex flex-col">
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
              <span className="text-xs font-medium truncate">{panel.title}</span>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => unpinPanel(panel.id)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
            <div className="h-[200px] overflow-auto p-2">
              <NodeTabContent
                runId={panel.runId}
                nodeId={panel.nodeId}
                tab={panel.tab}
                comparisonRunIds={isComparison ? runIds : undefined}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
