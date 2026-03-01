import { useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useStore } from '@/store'
import { GraphbookNode } from './GraphbookNode'
import { GraphbookEdge } from './GraphbookEdge'
import { GraphToolbar } from './GraphToolbar'

interface DagGraphProps {
  runId: string
}

const nodeTypes: NodeTypes = {
  graphbook: GraphbookNode,
}

const edgeTypes = {
  graphbook: GraphbookEdge,
}

function layoutNodes(
  graphNodes: Record<string, { name: string; is_source: boolean }>,
  graphEdges: { source: string; target: string }[],
): Node[] {
  // Simple topological layout: sources at top, layered by depth
  const adj = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  const allIds = Object.keys(graphNodes)

  for (const id of allIds) {
    adj.set(id, [])
    inDegree.set(id, 0)
  }
  for (const e of graphEdges) {
    adj.get(e.source)?.push(e.target)
    inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
  }

  // BFS for layers
  const layers: string[][] = []
  const queue = allIds.filter(id => (inDegree.get(id) ?? 0) === 0)
  const visited = new Set<string>()

  while (queue.length > 0) {
    const layer = [...queue]
    layers.push(layer)
    queue.length = 0
    for (const id of layer) {
      visited.add(id)
      for (const next of adj.get(id) ?? []) {
        inDegree.set(next, (inDegree.get(next) ?? 0) - 1)
        if ((inDegree.get(next) ?? 0) === 0 && !visited.has(next)) {
          queue.push(next)
        }
      }
    }
  }

  // Add any unvisited nodes (cycles) as a final layer
  const unvisited = allIds.filter(id => !visited.has(id))
  if (unvisited.length > 0) layers.push(unvisited)

  const nodes: Node[] = []
  const nodeWidth = 280
  const nodeHeight = 100
  const xGap = 60
  const yGap = 40

  for (let layerIdx = 0; layerIdx < layers.length; layerIdx++) {
    const layer = layers[layerIdx]
    const totalWidth = layer.length * nodeWidth + (layer.length - 1) * xGap
    const startX = -totalWidth / 2

    for (let i = 0; i < layer.length; i++) {
      const id = layer[i]
      const isInDag = visited.has(id)
      nodes.push({
        id,
        type: 'graphbook',
        position: {
          x: startX + i * (nodeWidth + xGap),
          y: layerIdx * (nodeHeight + yGap),
        },
        data: {
          nodeId: id,
          runId: id, // Will be overridden
          inDag: isInDag,
        },
      })
    }
  }

  return nodes
}

export function DagGraph({ runId }: DagGraphProps) {
  const runState = useStore(s => s.runs.get(runId))
  const storedPositions = useStore(s => s.nodePositions.get(runId))
  const updateNodePosition = useStore(s => s.updateNodePosition)
  const expandNode = useStore(s => s.expandNode)

  const graph = runState?.graph

  const initialNodes = useMemo(() => {
    if (!graph) return []
    const layouted = layoutNodes(graph.nodes, graph.edges)
    return layouted.map(n => {
      const stored = storedPositions?.get(n.id)
      return {
        ...n,
        position: stored ?? n.position,
        data: { ...n.data, runId },
      }
    })
  }, [graph, runId, storedPositions])

  const initialEdges = useMemo<Edge[]>(() => {
    if (!graph) return []
    return graph.edges.map((e, i) => ({
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      type: 'graphbook',
      data: { runId },
    }))
  }, [graph, runId])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Sync when graph data changes
  useMemo(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  const onNodeDragStop = useCallback((_: unknown, node: Node) => {
    updateNodePosition(runId, node.id, node.position)
  }, [runId, updateNodePosition])

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    expandNode(node.id)
  }, [expandNode])

  const onPaneClick = useCallback(() => {
    expandNode(null)
  }, [expandNode])

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
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
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
      </ReactFlow>
      <GraphToolbar runId={runId} />
    </div>
  )
}
