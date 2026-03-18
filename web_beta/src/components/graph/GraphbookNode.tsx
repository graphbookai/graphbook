import { memo, useCallback, useContext, useEffect } from 'react'
import { Handle, NodeResizer, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react'
import { useStore } from '@/store'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronRight, Maximize2 } from 'lucide-react'
import { NodeTabContainer } from '@/components/node-tabs/NodeTabContainer'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useContextMenu } from '@/hooks/useContextMenu'
import { ContextMenu } from '@/components/shared/ContextMenu'
import { ContextMenuItem } from '@/components/shared/ContextMenuItem'
import { DragContext } from './DagGraph'

interface GraphbookNodeData {
  nodeId: string
  runId: string
  inDag: boolean
}

export const GraphbookNode = memo(function GraphbookNode({ data, id }: NodeProps) {
  const { nodeId, runId, inDag } = data as unknown as GraphbookNodeData

  // Granular selectors — only re-render when THIS node's data changes, not on every log/metric append
  const nodeInfo = useStore(s => s.runs.get(runId)?.graph?.nodes[nodeId] ?? null)
  const hasErrors = useStore(s => (s.runs.get(runId)?.errors ?? []).some(e => e.node_name === nodeId))
  const runStatus = useStore(s => s.runs.get(runId)?.summary.status ?? null)
  const hasPendingAsk = useStore(s => {
    const asks = s.runs.get(runId)?.pendingAsks
    if (!asks || asks.size === 0) return false
    for (const a of asks.values()) { if (a.nodeName === nodeId) return true }
    return false
  })
  const isCollapsed = useStore(s => s.collapsedGraphNodes.has(id))
  const toggleGraphNode = useStore(s => s.toggleGraphNode)
  const dagDirection = useStore(s => s.dagDirection)
  const updateNodeInternals = useUpdateNodeInternals()
  useEffect(() => { updateNodeInternals(id) }, [dagDirection, id, updateNodeInternals])
  const resizingNodeId = useStore(s => s.resizingNodeId)
  const toggleNodeResize = useStore(s => s.toggleNodeResize)
  const updateNodeSize = useStore(s => s.updateNodeSize)
  const hideTabsOnDrag = useStore(s => s.settings.hideTabsOnDrag)
  const draggingNodeId = useContext(DragContext)
  const isDragging = draggingNodeId === id
  const isExpanded = !isCollapsed
  const isResizing = resizingNodeId === id
  const storedSize = useStore(s => s.nodeSizes.get(runId)?.get(nodeId))
  const contextMenu = useContextMenu()

  const onResize = useCallback((_event: unknown, params: { width: number; height: number }) => {
    updateNodeSize(runId, nodeId, { width: params.width, height: params.height })
  }, [runId, nodeId, updateNodeSize])

  if (!nodeInfo) return null

  const isRunning = runStatus === 'running' && nodeInfo.exec_count > 0
  const progress = nodeInfo.progress

  const borderColor = hasErrors
    ? 'border-red-500'
    : hasPendingAsk
    ? 'border-amber-500'
    : isRunning
    ? 'border-blue-500'
    : !inDag
    ? 'border-dashed border-muted-foreground/40'
    : 'border-border'

  return (
    <div
      className={cn(
        'bg-card rounded-lg border-2 shadow-sm transition-all',
        !storedSize && !isResizing && 'min-w-[240px] max-w-[320px]',
        borderColor,
        hasErrors && 'animate-shake',
        isRunning && !hasErrors && 'shadow-blue-500/20',
        hasPendingAsk && 'shadow-amber-500/30',
      )}
      style={storedSize ? { width: storedSize.width, minWidth: storedSize.width } : undefined}
      {...contextMenu.handlers}
    >
      {isResizing && (
        <NodeResizer minWidth={200} minHeight={80} onResize={onResize} />
      )}
      <ContextMenu isOpen={contextMenu.isOpen} position={contextMenu.position} onClose={contextMenu.close}>
        <ContextMenuItem
          label="Resize"
          icon={<Maximize2 className="w-4 h-4" />}
          onClick={() => { toggleNodeResize(id); contextMenu.close() }}
        />
      </ContextMenu>
      {!nodeInfo.is_source && (
        <Handle type="target" position={dagDirection === 'TB' ? Position.Top : Position.Left} className="!bg-muted-foreground !w-2 !h-2" />
      )}

      {/* Node header */}
      <div
        className="px-3 py-2 cursor-pointer select-none"
        onClick={() => toggleGraphNode(id)}
      >
        <div className="flex items-center gap-1.5">
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          )}
          <span className="text-sm font-medium truncate flex-1">{nodeInfo.func_name}</span>
          {nodeInfo.exec_count > 0 && (
            <span className="text-xs text-muted-foreground shrink-0">
              x{nodeInfo.exec_count.toLocaleString()}
            </span>
          )}
        </div>
        {nodeInfo.docstring && (
          <p className="text-xs text-muted-foreground mt-0.5 ml-5 line-clamp-1">{nodeInfo.docstring.split('\n')[0]}</p>
        )}

        {/* Config params */}
        {Object.keys(nodeInfo.params).length > 0 && (
          <div className="mt-1.5 ml-5 flex flex-wrap gap-1">
            {Object.entries(nodeInfo.params).slice(0, 3).map(([k, v]) => (
              <span key={k} className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                {k}: {String(v)}
              </span>
            ))}
            {Object.keys(nodeInfo.params).length > 3 && (
              <span className="text-[10px] text-muted-foreground">+{Object.keys(nodeInfo.params).length - 3}</span>
            )}
          </div>
        )}

        {/* Progress bar */}
        {progress && (
          <div className="mt-2 ml-5">
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

        {/* Non-DAG indicator */}
        {!inDag && (
          <span className="text-[10px] text-muted-foreground mt-1 ml-5 block">Not in DAG</span>
        )}
      </div>

      {/* Expanded tab content — optionally hidden during drag for performance */}
      {isExpanded && !(isDragging && hideTabsOnDrag) && (
        <div className="border-t border-border" onWheelCapture={e => e.stopPropagation()}>
          <ErrorBoundary label={`Node ${nodeId}`}>
            <NodeTabContainer runId={runId} nodeId={nodeId} />
          </ErrorBoundary>
        </div>
      )}
      {isExpanded && isDragging && hideTabsOnDrag && (
        <div className="border-t border-border h-[40px]" />
      )}

      <Handle type="source" position={dagDirection === 'TB' ? Position.Bottom : Position.Right} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  )
})
