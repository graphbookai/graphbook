import { useState, useMemo } from 'react'
import { useStore, type NodeTab } from '@/store'
import { cn } from '@/lib/utils'
import { Pin } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { NodeTabContent } from './NodeTabContent'

interface NodeTabContainerProps {
  runId: string
  nodeId: string
}

const allTabs: { key: NodeTab; label: string; alwaysShow: boolean }[] = [
  { key: 'info', label: 'Info', alwaysShow: true },
  { key: 'logs', label: 'Logs', alwaysShow: true },
  { key: 'metrics', label: 'Metrics', alwaysShow: false },
  { key: 'images', label: 'Images', alwaysShow: false },
  { key: 'audio', label: 'Audio', alwaysShow: false },
  { key: 'ask', label: 'Ask', alwaysShow: false },
]

export function NodeTabContainer({ runId, nodeId }: NodeTabContainerProps) {
  const [activeTab, setActiveTab] = useState<NodeTab>('info')
  const pinTab = useStore(s => s.pinTab)
  const run = useStore(s => s.runs.get(runId))

  const hasPendingAsk = run?.pendingAsks?.has(nodeId) ?? false
  const hasMetrics = !!run?.nodeMetrics?.[nodeId] && Object.keys(run.nodeMetrics[nodeId]).length > 0
  const hasImages = (run?.nodeImages?.[nodeId]?.length ?? 0) > 0
  const hasAudio = (run?.nodeAudio?.[nodeId]?.length ?? 0) > 0

  const visibleTabs = useMemo(() => {
    return allTabs.filter(tab => {
      if (tab.alwaysShow) return true
      switch (tab.key) {
        case 'metrics': return hasMetrics
        case 'images': return hasImages
        case 'audio': return hasAudio
        case 'ask': return hasPendingAsk
        default: return false
      }
    })
  }, [hasMetrics, hasImages, hasAudio, hasPendingAsk])

  // If the active tab is no longer visible, reset to 'info'
  const resolvedTab = visibleTabs.some(t => t.key === activeTab) ? activeTab : 'info'

  return (
    <div>
      {/* Tab bar */}
      <div className="flex items-center border-b border-border">
        <div className="flex flex-1">
          {visibleTabs.map(tab => (
            <button
              key={tab.key}
              className={cn(
                'px-3 py-1.5 text-xs font-medium transition-colors relative',
                resolvedTab === tab.key
                  ? 'text-foreground border-b-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              onClick={(e) => {
                e.stopPropagation()
                setActiveTab(tab.key)
              }}
            >
              {tab.label}
              {tab.key === 'ask' && hasPendingAsk && (
                <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-amber-500 rounded-full" />
              )}
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 mr-1"
          onClick={(e) => {
            e.stopPropagation()
            pinTab(runId, nodeId, resolvedTab)
          }}
          title="Pin this tab"
        >
          <Pin className="h-3 w-3" />
        </Button>
      </div>

      {/* Tab content */}
      <div className="p-3 max-h-[300px] overflow-auto" onClick={e => e.stopPropagation()}>
        <NodeTabContent runId={runId} nodeId={nodeId} tab={resolvedTab} />
      </div>
    </div>
  )
}
