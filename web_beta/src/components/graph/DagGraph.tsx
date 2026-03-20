import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  useNodesInitialized,
  type Node,
  type Edge,
  type NodeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import dagre from '@dagrejs/dagre'
import '@xyflow/react/dist/style.css'
import { useStore } from '@/store'
import { GraphbookNode } from './GraphbookNode'
import { GraphbookEdge } from './GraphbookEdge'
import { GraphToolbar } from './GraphToolbar'
import { DescriptionOverlay } from './DescriptionOverlay'
import { useContextMenu } from '@/hooks/useContextMenu'
import { GraphContextMenu } from './GraphContextMenu'

interface DagGraphProps {
  runId: string
}

const nodeTypes: NodeTypes = {
  graphbook: GraphbookNode,
}

const edgeTypes = {
  graphbook: GraphbookEdge,
}

export const DragContext = createContext<string | null>(null)

const DEFAULT_WIDTH = 280
const DEFAULT_HEIGHT = 100

function runDagreLayout(
  nodes: Node[],
  edges: Edge[],
  measured?: Map<string, { width: number; height: number }>,
  rankdir: 'TB' | 'LR' = 'TB',
): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir, nodesep: 50, ranksep: 60 })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) {
    const dims = measured?.get(node.id)
    g.setNode(node.id, {
      width: dims?.width ?? DEFAULT_WIDTH,
      height: dims?.height ?? DEFAULT_HEIGHT,
    })
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }

  dagre.layout(g)

  return nodes.map(node => {
    const pos = g.node(node.id)
    // dagre returns center coordinates; ReactFlow uses top-left
    return {
      ...node,
      position: {
        x: pos.x - pos.width / 2,
        y: pos.y - pos.height / 2,
      },
    }
  })
}

function getMeasuredDimensions(nodes: Node[]): Map<string, { width: number; height: number }> {
  const dims = new Map<string, { width: number; height: number }>()
  for (const n of nodes) {
    if (n.measured?.width && n.measured?.height) {
      dims.set(n.id, { width: n.measured.width, height: n.measured.height })
    }
  }
  return dims
}

function DagGraphInner({ runId }: DagGraphProps) {
  const runState = useStore(s => s.runs.get(runId))
  const updateNodePosition = useStore(s => s.updateNodePosition)
  const showMinimap = useStore(s => s.settings.showMinimap)
  const showControls = useStore(s => s.settings.showControls)
  const hideUncalled = useStore(s => s.settings.hideUncalledFunctions)
  const dagDirection = useStore(s => s.dagDirection)
  const graph = runState?.graph

  const { fitView, getNodes } = useReactFlow()
  const nodesInitialized = useNodesInitialized()
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])

  const initialLayoutDone = useRef(false)
  const edgesRef = useRef<Edge[]>([])

  // Keep a ref to graph so the memo can read latest data without depending on the object ref
  const graphRef = useRef(graph)
  graphRef.current = graph

  // Stable key that only changes when graph topology (node set or edge set) changes
  // Include exec_count info when hideUncalled is active so toggling the setting or
  // a node's first execution triggers a recompute.
  const structureKey = useMemo(() => {
    if (!graph) return ''
    const nodeKeys = Object.keys(graph.nodes).sort().join(',')
    const edgeKeys = graph.edges.map(e => `${e.source}->${e.target}`).sort().join(',')
    const execKey = hideUncalled
      ? Object.entries(graph.nodes).map(([id, n]) => `${id}:${n.exec_count > 0 ? 1 : 0}`).sort().join(',')
      : ''
    return `${nodeKeys}|${edgeKeys}|${execKey}|${hideUncalled}`
  }, [graph, hideUncalled])

  // Build base nodes and edges — only recomputes on structural changes, not exec_count/progress
  const { baseNodes, baseEdges } = useMemo(() => {
    const g = graphRef.current
    if (!g) return { baseNodes: [] as Node[], baseEdges: [] as Edge[] }
    const targetSet = new Set(g.edges.map(e => e.target))
    const sourceSet = new Set(g.edges.map(e => e.source))

    const visibleIds = Object.keys(g.nodes).filter(
      id => !hideUncalled || g.nodes[id].exec_count > 0
    )
    const visibleSet = new Set(visibleIds)

    const baseNodes: Node[] = visibleIds.map(id => ({
      id,
      type: 'graphbook' as const,
      position: { x: 0, y: 0 },
      data: {
        nodeId: id,
        runId,
        inDag: sourceSet.has(id) || targetSet.has(id) || g.nodes[id].is_source,
      },
    }))

    const baseEdges: Edge[] = g.edges
      .filter(e => visibleSet.has(e.source) && visibleSet.has(e.target))
      .map(e => ({
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        type: 'graphbook',
        data: { runId },
      }))

    return { baseNodes, baseEdges }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey, runId])

  // Set initial nodes/edges with default-size dagre layout
  useEffect(() => {
    if (baseNodes.length === 0) {
      setNodes([])
      setEdges([])
      return
    }
    const laid = runDagreLayout(baseNodes, baseEdges, undefined, dagDirection)
    setNodes(laid)
    setEdges(baseEdges)
    edgesRef.current = baseEdges
    initialLayoutDone.current = false
  }, [baseNodes, baseEdges, setNodes, setEdges, dagDirection])

  // After initial measurement, re-layout with real dimensions
  useEffect(() => {
    if (!nodesInitialized || initialLayoutDone.current || nodes.length === 0) return

    const currentNodes = getNodes()
    const dims = getMeasuredDimensions(currentNodes)
    if (dims.size === currentNodes.length) {
      initialLayoutDone.current = true
      const laid = runDagreLayout(currentNodes, edgesRef.current, dims, dagDirection)
      setNodes(laid)
      requestAnimationFrame(() => fitView({ duration: 200 }))
    }
  }, [nodesInitialized, nodes.length, getNodes, setNodes, fitView, dagDirection])

  // Relayout only when explicitly triggered (expand/collapse/reset), not on content growth
  const layoutTrigger = useStore(s => s.layoutTrigger)

  useEffect(() => {
    if (!initialLayoutDone.current || layoutTrigger === 0) return

    // Delay for React to measure new dimensions after expand/collapse
    const timer = setTimeout(() => {
      const currentNodes = getNodes()
      const dims = getMeasuredDimensions(currentNodes)
      if (dims.size > 0) {
        const laid = runDagreLayout(currentNodes, edgesRef.current, dims, dagDirection)
        setNodes(laid)
      }
    }, 100)

    return () => clearTimeout(timer)
  }, [layoutTrigger, getNodes, setNodes, dagDirection])

  const onResetLayout = useCallback(() => {
    const currentNodes = getNodes()
    const dims = getMeasuredDimensions(currentNodes)
    if (dims.size > 0) {
      const laid = runDagreLayout(currentNodes, edgesRef.current, dims, dagDirection)
      setNodes(laid)
      requestAnimationFrame(() => fitView({ duration: 200 }))
    }
  }, [getNodes, setNodes, fitView, dagDirection])

  const resizingNodeId = useStore(s => s.resizingNodeId)
  const toggleNodeResize = useStore(s => s.toggleNodeResize)
  const contextMenu = useContextMenu()

  // Escape key clears resizing state
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && resizingNodeId !== null) {
        toggleNodeResize(resizingNodeId)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [resizingNodeId, toggleNodeResize])

  const onPaneClick = useCallback(() => {
    if (resizingNodeId !== null) {
      toggleNodeResize(resizingNodeId)
    }
  }, [resizingNodeId, toggleNodeResize])

  const onPaneContextMenu = useCallback((event: MouseEvent | React.MouseEvent) => {
    event.preventDefault()
    contextMenu.open(event as React.MouseEvent)
  }, [contextMenu])

  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null)

  const onNodeDragStart = useCallback((_: unknown, node: Node) => {
    setDraggingNodeId(node.id)
  }, [])

  const onNodeDragStop = useCallback((_: unknown, node: Node) => {
    setDraggingNodeId(null)
    updateNodePosition(runId, node.id, node.position)
  }, [runId, updateNodePosition])

  if (!graph) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Loading graph...</p>
      </div>
    )
  }

  return (
    <DragContext.Provider value={draggingNodeId}>
      <div className="h-full w-full relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStart={onNodeDragStart}
          onNodeDragStop={onNodeDragStop}
          onPaneClick={onPaneClick}
          onPaneContextMenu={onPaneContextMenu}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="!bg-background" />
          {showControls && <Controls className="!bg-card !border-border !shadow-sm" />}
          {showMinimap && (
            <MiniMap
              className="!bg-card !border-border"
              nodeColor={() => 'oklch(0.556 0 0)'}
              maskColor="rgba(0, 0, 0, 0.3)"
            />
          )}
          <GraphToolbar onResetLayout={onResetLayout} runId={runId} />
        </ReactFlow>
        <DescriptionOverlay runId={runId} />
        <GraphContextMenu isOpen={contextMenu.isOpen} position={contextMenu.position} onClose={contextMenu.close} />
      </div>
    </DragContext.Provider>
  )
}

export function DagGraph({ runId }: DagGraphProps) {
  return (
    <ReactFlowProvider>
      <DagGraphInner runId={runId} />
    </ReactFlowProvider>
  )
}
