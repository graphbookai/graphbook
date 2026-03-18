import { useState, useMemo, useRef } from 'react'
import { useStore, type NodeTab } from '@/store'
import { cn } from '@/lib/utils'
import { Pin } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { NodeTabContent } from './NodeTabContent'
import { useComparisonContext } from '@/hooks/useComparisonContext'

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
  const runs = useStore(s => s.runs)
  const { isComparison, runIds: comparisonRunIds } = useComparisonContext()

  const hasPendingAsk = useMemo(() => {
    const asks = run?.pendingAsks
    if (!asks || asks.size === 0) return false
    for (const a of asks.values()) { if (a.nodeName === nodeId) return true }
    return false
  }, [run?.pendingAsks, nodeId])

  // In comparison mode, aggregate data availability across all runs
  const hasMetrics = useMemo(() => {
    if (isComparison) {
      return comparisonRunIds.some(rid => {
        const r = runs.get(rid)
        return !!r?.nodeMetrics?.[nodeId] && Object.keys(r.nodeMetrics[nodeId]).length > 0
      })
    }
    return !!run?.nodeMetrics?.[nodeId] && Object.keys(run.nodeMetrics[nodeId]).length > 0
  }, [isComparison, comparisonRunIds, runs, run, nodeId])

  const hasImages = useMemo(() => {
    if (isComparison) {
      return comparisonRunIds.some(rid => (runs.get(rid)?.nodeImages?.[nodeId]?.length ?? 0) > 0)
    }
    return (run?.nodeImages?.[nodeId]?.length ?? 0) > 0
  }, [isComparison, comparisonRunIds, runs, run, nodeId])

  const hasAudio = useMemo(() => {
    if (isComparison) {
      return comparisonRunIds.some(rid => (runs.get(rid)?.nodeAudio?.[nodeId]?.length ?? 0) > 0)
    }
    return (run?.nodeAudio?.[nodeId]?.length ?? 0) > 0
  }, [isComparison, comparisonRunIds, runs, run, nodeId])

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

  // Only reset to 'info' if the user hasn't explicitly chosen a tab yet.
  // Once the user clicks a tab, keep it even if it temporarily leaves visibleTabs
  // (e.g., while data is still loading via WebSocket).
  const userChoseTab = useRef(false)
  const isActiveVisible = visibleTabs.some(t => t.key === activeTab)
  const resolvedTab = isActiveVisible ? activeTab : (userChoseTab.current ? activeTab : 'info')

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
                userChoseTab.current = true
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
        <NodeTabContent runId={runId} nodeId={nodeId} tab={resolvedTab} comparisonRunIds={isComparison ? comparisonRunIds : undefined} />
      </div>
    </div>
  )
}
