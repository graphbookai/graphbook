import { useCallback, useEffect, useMemo, useRef } from 'react'
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
  type NodeChange,
  BackgroundVariant,
} from '@xyflow/react'
import dagre from '@dagrejs/dagre'
import '@xyflow/react/dist/style.css'
import { useStore } from '@/store'
import { GraphbookNode } from './GraphbookNode'
import { GraphbookEdge } from './GraphbookEdge'
import { GraphToolbar } from './GraphToolbar'
import { DescriptionOverlay } from './DescriptionOverlay'

interface DagGraphProps {
  runId: string
}

const nodeTypes: NodeTypes = {
  graphbook: GraphbookNode,
}

const edgeTypes = {
  graphbook: GraphbookEdge,
}

const DEFAULT_WIDTH = 280
const DEFAULT_HEIGHT = 100

function runDagreLayout(
  nodes: Node[],
  edges: Edge[],
  measured?: Map<string, { width: number; height: number }>,
): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 60 })
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
  const graph = runState?.graph

  const { fitView, getNodes } = useReactFlow()
  const nodesInitialized = useNodesInitialized()
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])

  const initialLayoutDone = useRef(false)
  const edgesRef = useRef<Edge[]>([])
  const layoutTimerRef = useRef<ReturnType<typeof setTimeout>>()

  // Build base nodes and edges from graph data
  const { baseNodes, baseEdges } = useMemo(() => {
    if (!graph) return { baseNodes: [] as Node[], baseEdges: [] as Edge[] }
    const targetSet = new Set(graph.edges.map(e => e.target))
    const sourceSet = new Set(graph.edges.map(e => e.source))

    const baseNodes: Node[] = Object.keys(graph.nodes).map(id => ({
      id,
      type: 'graphbook' as const,
      position: { x: 0, y: 0 },
      data: {
        nodeId: id,
        runId,
        inDag: sourceSet.has(id) || targetSet.has(id) || graph.nodes[id].is_source,
      },
    }))

    const baseEdges: Edge[] = graph.edges.map(e => ({
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      type: 'graphbook',
      data: { runId },
    }))

    return { baseNodes, baseEdges }
  }, [graph, runId])

  // Set initial nodes/edges with default-size dagre layout
  useEffect(() => {
    if (baseNodes.length === 0) {
      setNodes([])
      setEdges([])
      return
    }
    const laid = runDagreLayout(baseNodes, baseEdges)
    setNodes(laid)
    setEdges(baseEdges)
    edgesRef.current = baseEdges
    initialLayoutDone.current = false
  }, [baseNodes, baseEdges, setNodes, setEdges])

  // After initial measurement, re-layout with real dimensions
  useEffect(() => {
    if (!nodesInitialized || initialLayoutDone.current || nodes.length === 0) return

    const currentNodes = getNodes()
    const dims = getMeasuredDimensions(currentNodes)
    if (dims.size === currentNodes.length) {
      initialLayoutDone.current = true
      const laid = runDagreLayout(currentNodes, edgesRef.current, dims)
      setNodes(laid)
      requestAnimationFrame(() => fitView({ duration: 200 }))
    }
  }, [nodesInitialized, nodes.length, getNodes, setNodes, fitView])

  // Detect dimension changes (from expand/collapse) and re-layout
  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    onNodesChange(changes)
    if (!initialLayoutDone.current) return

    const hasDimChange = changes.some(c => c.type === 'dimensions')
    if (hasDimChange) {
      clearTimeout(layoutTimerRef.current)
      layoutTimerRef.current = setTimeout(() => {
        const currentNodes = getNodes()
        const dims = getMeasuredDimensions(currentNodes)
        if (dims.size > 0) {
          const laid = runDagreLayout(currentNodes, edgesRef.current, dims)
          setNodes(laid)
        }
      }, 50)
    }
  }, [onNodesChange, getNodes, setNodes])

  // Clean up timer on unmount
  useEffect(() => {
    return () => clearTimeout(layoutTimerRef.current)
  }, [])

  const onResetLayout = useCallback(() => {
    const currentNodes = getNodes()
    const dims = getMeasuredDimensions(currentNodes)
    if (dims.size > 0) {
      const laid = runDagreLayout(currentNodes, edgesRef.current, dims)
      setNodes(laid)
      requestAnimationFrame(() => fitView({ duration: 200 }))
    }
  }, [getNodes, setNodes, fitView])

  const onNodeDragStop = useCallback((_: unknown, node: Node) => {
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
    <div className="h-full w-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="!bg-background" />
        <Controls className="!bg-card !border-border !shadow-sm" />
        <MiniMap
          className="!bg-card !border-border"
          nodeColor={() => 'oklch(0.556 0 0)'}
          maskColor="rgba(0, 0, 0, 0.3)"
        />
        <GraphToolbar onResetLayout={onResetLayout} />
      </ReactFlow>
      <DescriptionOverlay runId={runId} />
    </div>
  )
}

export function DagGraph({ runId }: DagGraphProps) {
  return (
    <ReactFlowProvider>
      <DagGraphInner runId={runId} />
    </ReactFlowProvider>
  )
}
