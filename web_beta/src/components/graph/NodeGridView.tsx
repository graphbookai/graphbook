import { memo, useMemo, useState } from 'react'
import { useStore } from '@/store'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Network } from 'lucide-react'
import { NodeTabContainer } from '@/components/node-tabs/NodeTabContainer'
import { topologicalSort } from '@/lib/graph'

// Extracted to module level so React preserves instance identity across parent re-renders.
// This prevents NodeTabContainer (and its active tab state) from being unmounted/remounted.
const NodeCard = memo(function NodeCard({
  runId,
  nodeId,
  isDag,
  isExpanded,
  onToggle,
}: {
  runId: string
  nodeId: string
  isDag: boolean
  isExpanded: boolean
  onToggle: () => void
}) {
  const node = useStore(s => s.runs.get(runId)?.graph?.nodes[nodeId])
  const hasErrors = useStore(s => (s.runs.get(runId)?.errors ?? []).some(e => e.node_name === nodeId))
  const isRunning = useStore(s => s.runs.get(runId)?.summary.status === 'running') && (node?.exec_count ?? 0) > 0

  if (!node) return null

  const progress = node.progress
  const borderColor = hasErrors
    ? 'border-red-500'
    : isRunning
    ? 'border-blue-500'
    : !isDag
    ? 'border-dashed border-muted-foreground/40'
    : 'border-border'

  return (
    <div
      className={cn(
        'border-2 rounded-lg transition-all cursor-pointer',
        borderColor,
        !isDag && 'opacity-80',
      )}
      onClick={onToggle}
    >
      <div className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate flex-1">{node.func_name}</span>
          {node.exec_count > 0 && (
            <span className="text-xs text-muted-foreground shrink-0">
              x{node.exec_count.toLocaleString()}
            </span>
          )}
        </div>

        {node.docstring && (
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
            {node.docstring.split('\n')[0]}
          </p>
        )}

        {Object.keys(node.params).length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {Object.entries(node.params).slice(0, 3).map(([k, v]) => (
              <span key={k} className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                {k}: {String(v)}
              </span>
            ))}
            {Object.keys(node.params).length > 3 && (
              <span className="text-[10px] text-muted-foreground">
                +{Object.keys(node.params).length - 3}
              </span>
            )}
          </div>
        )}

        {progress && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>{progress.name ?? 'Progress'}</span>
              <span>{Math.round((progress.current / progress.total) * 100)}%</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {isExpanded && (
        <div className="border-t border-border" onClick={e => e.stopPropagation()}>
          <NodeTabContainer runId={runId} nodeId={nodeId} />
        </div>
      )}
    </div>
  )
})

interface NodeGridViewProps {
  runId: string
}

export function NodeGridView({ runId }: NodeGridViewProps) {
  const graph = useStore(s => s.runs.get(runId)?.graph)
  const collapseByDefault = useStore(s => s.settings.collapseNodesByDefault)
  const hideUncalled = useStore(s => s.settings.hideUncalledFunctions)
  const setDesktopViewMode = useStore(s => s.setDesktopViewMode)

  const allNodeIds = useMemo(() => graph
    ? Object.keys(graph.nodes).filter(id => !hideUncalled || graph.nodes[id].exec_count > 0)
    : [], [graph, hideUncalled])

  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() => {
    return collapseByDefault ? new Set() : new Set(allNodeIds)
  })

  if (!graph) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Loading nodes...</p>
      </div>
    )
  }

  const targetSet = new Set(graph.edges.map(e => e.target))
  const sourceSet = new Set(graph.edges.map(e => e.source))
  const dagNodeIds = allNodeIds.filter(id => sourceSet.has(id) || targetSet.has(id) || graph.nodes[id].is_source)
  const nonDagNodeIds = allNodeIds.filter(id => !dagNodeIds.includes(id))
  const sorted = topologicalSort(dagNodeIds, graph.edges)

  const toggleExpanded = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }

  return (
    <ScrollArea className="h-full">
      <div className="flex items-center gap-2 px-3 pt-2">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs gap-1.5"
          onClick={() => setDesktopViewMode('graph')}
        >
          <Network className="h-3.5 w-3.5" />
          Graph View
        </Button>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 p-3">
        {sorted.map(nodeId => (
          <NodeCard
            key={nodeId}
            runId={runId}
            nodeId={nodeId}
            isDag
            isExpanded={expandedNodes.has(nodeId)}
            onToggle={() => toggleExpanded(nodeId)}
          />
        ))}
      </div>

      {nonDagNodeIds.length > 0 && (
        <>
          <div className="flex items-center gap-2 px-3 pt-2 pb-1">
            <div className="h-px flex-1 bg-border border-dashed" />
            <span className="text-xs text-muted-foreground">Not in DAG</span>
            <div className="h-px flex-1 bg-border border-dashed" />
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 p-3 pt-1">
            {nonDagNodeIds.map(nodeId => (
              <NodeCard
                key={nodeId}
                runId={runId}
                nodeId={nodeId}
                isDag={false}
                isExpanded={expandedNodes.has(nodeId)}
                onToggle={() => toggleExpanded(nodeId)}
              />
            ))}
          </div>
        </>
      )}
    </ScrollArea>
  )
}
