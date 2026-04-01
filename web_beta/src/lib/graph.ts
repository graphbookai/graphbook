import type { GraphData } from '@/lib/api'
import type { RunState } from '@/store'

export function topologicalSort(
  nodeIds: string[],
  edges: { source: string; target: string }[],
): string[] {
  const adj = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  const nodeSet = new Set(nodeIds)

  for (const id of nodeIds) {
    adj.set(id, [])
    inDegree.set(id, 0)
  }
  for (const e of edges) {
    if (nodeSet.has(e.source) && nodeSet.has(e.target)) {
      adj.get(e.source)?.push(e.target)
      inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1)
    }
  }

  const result: string[] = []
  const queue = nodeIds
    .filter(id => (inDegree.get(id) ?? 0) === 0)
    .sort()

  while (queue.length > 0) {
    const id = queue.shift()!
    result.push(id)
    for (const next of (adj.get(id) ?? []).sort()) {
      inDegree.set(next, (inDegree.get(next) ?? 0) - 1)
      if ((inDegree.get(next) ?? 0) === 0) queue.push(next)
    }
  }

  // Add remaining cycle participants alphabetically
  for (const id of nodeIds.sort()) {
    if (!result.includes(id)) result.push(id)
  }

  return result
}

export interface UnionGraph extends GraphData {
  nodePresence: Map<string, Set<string>> // nodeId → set of runIds that contain it
}

export function computeUnionGraph(
  runs: Map<string, RunState>,
  runIds: string[],
): UnionGraph {
  const nodes: UnionGraph['nodes'] = {}
  const edgeSet = new Set<string>()
  const edges: { source: string; target: string }[] = []
  const nodePresence = new Map<string, Set<string>>()

  for (const runId of runIds) {
    const run = runs.get(runId)
    const graph = run?.graph
    if (!graph) continue

    for (const [nodeId, nodeData] of Object.entries(graph.nodes)) {
      if (!nodePresence.has(nodeId)) {
        nodePresence.set(nodeId, new Set())
      }
      nodePresence.get(nodeId)!.add(runId)

      // Use first run's data as canonical
      if (!nodes[nodeId]) {
        nodes[nodeId] = { ...nodeData }
      }
    }

    for (const edge of graph.edges) {
      const key = `${edge.source}->${edge.target}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        edges.push(edge)
      }
    }
  }

  return { nodes, edges, workflow_description: null, has_pausable: false, paused: false, nodePresence }
}
