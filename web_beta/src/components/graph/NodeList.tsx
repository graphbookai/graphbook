import { useState } from 'react'
import { useStore } from '@/store'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { NodeTabContainer } from '@/components/node-tabs/NodeTabContainer'
import { topologicalSort } from '@/lib/graph'

interface NodeListProps {
  runId: string
}

export function NodeList({ runId }: NodeListProps) {
  const run = useStore(s => s.runs.get(runId))
  const hideUncalled = useStore(s => s.settings.hideUncalledFunctions)
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set())

  const graph = run?.graph
  if (!graph) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Loading nodes...</p>
      </div>
    )
  }

  const toggleNode = (nodeId: string) => {
    setCollapsedNodes(prev => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)
      } else {
        next.add(nodeId)
      }
      return next
    })
  }

  const allNodeIds = Object.keys(graph.nodes).filter(
    id => !hideUncalled || graph.nodes[id].exec_count > 0
  )

  // Separate DAG nodes from non-DAG nodes
  const targetSet = new Set(graph.edges.map(e => e.target))
  const sourceSet = new Set(graph.edges.map(e => e.source))
  const dagNodeIds = allNodeIds.filter(id => sourceSet.has(id) || targetSet.has(id) || graph.nodes[id].is_source)
  const nonDagNodeIds = allNodeIds.filter(id => !dagNodeIds.includes(id))

  // Simple topological sort for DAG nodes
  const sorted = topologicalSort(dagNodeIds, graph.edges)

  return (
    <ScrollArea className="h-full">
      <div className="p-3 space-y-2">
        {sorted.map(nodeId => {
          const node = graph.nodes[nodeId]
          const isExpanded = !collapsedNodes.has(nodeId)
          const hasErrors = (run?.errors ?? []).some(e => e.node_name === nodeId)

          return (
            <div key={nodeId} className={cn(
              'border rounded-lg transition-colors',
              hasErrors ? 'border-red-500' : 'border-border',
            )}>
              <button
                className="w-full text-left px-3 py-2.5 hover:bg-accent/30 transition-colors"
                onClick={() => toggleNode(nodeId)}
              >
                <div className="flex items-center gap-2">
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  )}
                  <span className="text-sm font-medium truncate flex-1">{node.func_name}</span>
                  {node.exec_count > 0 && (
                    <span className="text-xs text-muted-foreground shrink-0">x{node.exec_count.toLocaleString()}</span>
                  )}
                </div>
                {node.docstring && (
                  <p className="text-xs text-muted-foreground mt-0.5 ml-5.5 line-clamp-1">{node.docstring.split('\n')[0]}</p>
                )}
                {node.progress && (
                  <div className="mt-1.5 ml-5.5 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{ width: `${(node.progress.current / node.progress.total) * 100}%` }}
                    />
                  </div>
                )}
              </button>
              {isExpanded && (
                <div className="border-t border-border">
                  <NodeTabContainer runId={runId} nodeId={nodeId} />
                </div>
              )}
            </div>
          )
        })}

        {/* Non-DAG nodes */}
        {nonDagNodeIds.length > 0 && (
          <>
            <div className="flex items-center gap-2 pt-2">
              <div className="h-px flex-1 bg-border border-dashed" />
              <span className="text-xs text-muted-foreground">Not in DAG</span>
              <div className="h-px flex-1 bg-border border-dashed" />
            </div>
            {nonDagNodeIds.map(nodeId => {
              const node = graph.nodes[nodeId]
              const isExpanded = !collapsedNodes.has(nodeId)

              return (
                <div key={nodeId} className="border border-dashed border-muted-foreground/40 rounded-lg opacity-80">
                  <button
                    className="w-full text-left px-3 py-2.5 hover:bg-accent/30 transition-colors"
                    onClick={() => toggleNode(nodeId)}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      )}
                      <span className="text-sm font-medium truncate flex-1">{node.func_name}</span>
                      {node.exec_count > 0 && (
                        <span className="text-xs text-muted-foreground shrink-0">x{node.exec_count.toLocaleString()}</span>
                      )}
                    </div>
                    {node.docstring && (
                      <p className="text-xs text-muted-foreground mt-0.5 ml-5.5 line-clamp-1">{node.docstring.split('\n')[0]}</p>
                    )}
                  </button>
                  {isExpanded && (
                    <div className="border-t border-border">
                      <NodeTabContainer runId={runId} nodeId={nodeId} />
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>
    </ScrollArea>
  )
}

