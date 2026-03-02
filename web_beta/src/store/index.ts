import { create } from 'zustand'
import type { RunSummary, GraphData, LogEntry, ErrorEntry } from '@/lib/api'
import type { WsEvent } from '@/lib/ws'

export interface NodeState {
  name: string
  funcName: string
  docstring: string | null
  configKey: string | null
  params: Record<string, unknown>
  executionCount: number
  isSource: boolean
  progress: { current: number; total: number; name?: string } | null
  inDag: boolean
  hasPendingAsk: boolean
}

export interface AskPrompt {
  askId: string
  nodeName: string
  question: string
  options: string[] | null
  timeoutSeconds: number | null
  receivedAt: Date
}

export type NodeTab = 'info' | 'logs' | 'metrics' | 'ask'

export interface PinnedPanel {
  id: string
  runId: string
  nodeId: string
  tab: NodeTab
  title: string
}

export interface RunState {
  summary: RunSummary
  graph: GraphData | null
  logs: LogEntry[]
  errors: ErrorEntry[]
  nodeMetrics: Record<string, Record<string, { step: number; value: number }[]>>
  inspections: Record<string, Record<string, unknown>>
  pendingAsks: Map<string, AskPrompt>
  loaded: boolean
}

interface GraphbookStore {
  // Connection
  connected: boolean
  reconnecting: boolean
  setConnectionStatus: (connected: boolean, reconnecting: boolean) => void

  // Runs
  runs: Map<string, RunState>
  selectedRunId: string | null
  activeRunId: string | null

  // Node interaction (graph view)
  collapsedGraphNodes: Set<string>

  // Pinned panels
  pinnedPanels: PinnedPanel[]

  // Node positions (per run, session-only)
  nodePositions: Map<string, Map<string, { x: number; y: number }>>

  // Node list panel (desktop)
  nodeListCollapsed: boolean
  toggleNodeList: () => void

  // Theme
  theme: 'dark' | 'light'

  // Actions
  setRuns: (summaries: RunSummary[], activeRunId: string | null) => void
  updateRunSummary: (summary: RunSummary) => void
  setRunGraph: (runId: string, graph: GraphData) => void
  setRunLogs: (runId: string, logs: LogEntry[]) => void
  appendRunLog: (runId: string, log: LogEntry) => void
  setRunErrors: (runId: string, errors: ErrorEntry[]) => void
  appendRunError: (runId: string, error: ErrorEntry) => void
  appendMetric: (runId: string, nodeId: string, name: string, step: number, value: number) => void
  updateNodeProgress: (runId: string, nodeId: string, progress: { current: number; total: number; name?: string } | null) => void
  updateNodeRegistration: (runId: string, data: Record<string, unknown>) => void
  incrementNodeExecution: (runId: string, nodeId: string) => void
  addEdge: (runId: string, source: string, target: string) => void
  updateInspection: (runId: string, nodeId: string, name: string, data: unknown) => void
  setWorkflowDescription: (runId: string, description: string) => void

  selectRun: (runId: string | null) => void
  toggleGraphNode: (nodeId: string) => void
  collapseAllGraphNodes: () => void
  pinTab: (runId: string, nodeId: string, tab: NodeTab) => void
  unpinPanel: (panelId: string) => void

  updateNodePosition: (runId: string, nodeId: string, pos: { x: number; y: number }) => void
  resetLayout: (runId: string) => void

  addAskPrompt: (runId: string, prompt: AskPrompt) => void
  removeAskPrompt: (runId: string, askId: string) => void

  toggleTheme: () => void

  processWsEvents: (runId: string, events: WsEvent[]) => void
}

function ensureRun(state: GraphbookStore, runId: string): RunState {
  let run = state.runs.get(runId)
  if (!run) {
    run = {
      summary: {
        id: runId,
        script_path: 'direct',
        args: [],
        status: 'running',
        started_at: new Date().toISOString(),
        ended_at: null,
        exit_code: null,
        node_count: 0,
        edge_count: 0,
        log_count: 0,
        error_count: 0,
      },
      graph: null,
      logs: [],
      errors: [],
      nodeMetrics: {},
      inspections: {},
      pendingAsks: new Map(),
      loaded: false,
    }
    state.runs.set(runId, run)
  }
  return run
}

export const useStore = create<GraphbookStore>((set, get) => ({
  connected: false,
  reconnecting: false,
  setConnectionStatus: (connected, reconnecting) => set({ connected, reconnecting }),

  runs: new Map(),
  selectedRunId: null,
  activeRunId: null,

  collapsedGraphNodes: new Set<string>(),

  pinnedPanels: [],

  nodePositions: new Map(),

  nodeListCollapsed: false,
  toggleNodeList: () => set(state => ({ nodeListCollapsed: !state.nodeListCollapsed })),

  theme: 'dark',

  setRuns: (summaries, activeRunId) => set(state => {
    const runs = new Map(state.runs)
    for (const s of summaries) {
      const existing = runs.get(s.id)
      if (existing) {
        existing.summary = s
      } else {
        runs.set(s.id, {
          summary: s,
          graph: null,
          logs: [],
          errors: [],
          nodeMetrics: {},
          inspections: {},
          pendingAsks: new Map(),
          loaded: false,
        })
      }
    }
    // Auto-select the most recent run if none selected
    let selectedRunId = state.selectedRunId
    if (!selectedRunId && summaries.length > 0) {
      selectedRunId = activeRunId ?? summaries[summaries.length - 1].id
    }
    return { runs, activeRunId, selectedRunId }
  }),

  updateRunSummary: (summary) => set(state => {
    const runs = new Map(state.runs)
    const existing = runs.get(summary.id)
    if (existing) {
      existing.summary = summary
    }
    return { runs }
  }),

  setRunGraph: (runId, graph) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      run.graph = graph
      run.loaded = true
    }
    return { runs }
  }),

  setRunLogs: (runId, logs) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) run.logs = logs
    return { runs }
  }),

  appendRunLog: (runId, log) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) run.logs = [...run.logs, log]
    return { runs }
  }),

  setRunErrors: (runId, errors) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) run.errors = errors
    return { runs }
  }),

  appendRunError: (runId, error) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) run.errors = [...run.errors, error]
    return { runs }
  }),

  appendMetric: (runId, nodeId, name, step, value) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      if (!run.nodeMetrics[nodeId]) run.nodeMetrics[nodeId] = {}
      if (!run.nodeMetrics[nodeId][name]) run.nodeMetrics[nodeId][name] = []
      run.nodeMetrics[nodeId][name] = [...run.nodeMetrics[nodeId][name], { step, value }]
    }
    return { runs }
  }),

  updateNodeProgress: (runId, nodeId, progress) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run?.graph?.nodes[nodeId]) {
      run.graph = {
        ...run.graph,
        nodes: {
          ...run.graph.nodes,
          [nodeId]: { ...run.graph.nodes[nodeId], progress },
        },
      }
    }
    return { runs }
  }),

  updateNodeRegistration: (runId, data) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      const nodeId = (data.node_id as string) || ''
      if (!run.graph) {
        run.graph = { nodes: {}, edges: [], workflow_description: null }
      }
      if (!run.graph.nodes[nodeId]) {
        run.graph.nodes[nodeId] = {
          name: nodeId,
          func_name: (data.func_name as string) || '',
          docstring: (data.docstring as string) || null,
          config_key: (data.config_key as string) || null,
          exec_count: 0,
          is_source: true,
          params: {},
          progress: null,
        }
      }
      run.summary.node_count = Object.keys(run.graph.nodes).length
    }
    return { runs }
  }),

  incrementNodeExecution: (runId, nodeId) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run?.graph?.nodes[nodeId]) {
      run.graph = {
        ...run.graph,
        nodes: {
          ...run.graph.nodes,
          [nodeId]: {
            ...run.graph.nodes[nodeId],
            exec_count: run.graph.nodes[nodeId].exec_count + 1,
          },
        },
      }
    }
    return { runs }
  }),

  addEdge: (runId, source, target) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run?.graph) {
      const exists = run.graph.edges.some(e => e.source === source && e.target === target)
      if (!exists) {
        run.graph = {
          ...run.graph,
          edges: [...run.graph.edges, { source, target }],
          nodes: {
            ...run.graph.nodes,
            ...(run.graph.nodes[target] ? {
              [target]: { ...run.graph.nodes[target], is_source: false },
            } : {}),
          },
        }
        run.summary.edge_count = run.graph.edges.length
      }
    }
    return { runs }
  }),

  updateInspection: (runId, nodeId, name, data) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      if (!run.inspections[nodeId]) run.inspections[nodeId] = {}
      run.inspections[nodeId] = { ...run.inspections[nodeId], [name]: data }
    }
    return { runs }
  }),

  setWorkflowDescription: (runId, description) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run?.graph) {
      run.graph = { ...run.graph, workflow_description: description }
    }
    return { runs }
  }),

  selectRun: (runId) => set({ selectedRunId: runId }),
  toggleGraphNode: (nodeId) => set(state => {
    const next = new Set(state.collapsedGraphNodes)
    if (next.has(nodeId)) {
      next.delete(nodeId)
    } else {
      next.add(nodeId)
    }
    return { collapsedGraphNodes: next }
  }),
  collapseAllGraphNodes: () => set(state => {
    // Add all current graph node IDs to collapsed set
    const selectedRun = state.selectedRunId ? state.runs.get(state.selectedRunId) : null
    const allIds = selectedRun?.graph ? Object.keys(selectedRun.graph.nodes) : []
    return { collapsedGraphNodes: new Set(allIds) }
  }),
  pinTab: (runId, nodeId, tab) => set(state => {
    const run = state.runs.get(runId)
    const nodeName = run?.graph?.nodes[nodeId]?.func_name || nodeId
    const panel: PinnedPanel = {
      id: `${runId}:${nodeId}:${tab}:${Date.now()}`,
      runId,
      nodeId,
      tab,
      title: `${nodeName} — ${tab.charAt(0).toUpperCase() + tab.slice(1)}`,
    }
    return { pinnedPanels: [...state.pinnedPanels, panel] }
  }),

  unpinPanel: (panelId) => set(state => ({
    pinnedPanels: state.pinnedPanels.filter(p => p.id !== panelId),
  })),

  updateNodePosition: (runId, nodeId, pos) => set(state => {
    const positions = new Map(state.nodePositions)
    if (!positions.has(runId)) positions.set(runId, new Map())
    positions.get(runId)!.set(nodeId, pos)
    return { nodePositions: positions }
  }),

  resetLayout: (runId) => set(state => {
    const positions = new Map(state.nodePositions)
    positions.delete(runId)
    return { nodePositions: positions }
  }),

  addAskPrompt: (runId, prompt) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      const asks = new Map(run.pendingAsks)
      asks.set(prompt.askId, prompt)
      run.pendingAsks = asks
    }
    return { runs }
  }),

  removeAskPrompt: (runId, askId) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      const asks = new Map(run.pendingAsks)
      asks.delete(askId)
      run.pendingAsks = asks
    }
    return { runs }
  }),

  toggleTheme: () => set(state => {
    const next = state.theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    return { theme: next }
  }),

  processWsEvents: (runId, events) => {
    const state = get()
    ensureRun(state, runId)
    for (const event of events) {
      const etype = event.type
      const nodeId = event.node as string | undefined
      const data = (event.data ?? event) as Record<string, unknown>

      switch (etype) {
        case 'log':
          state.appendRunLog(runId, {
            timestamp: (event.timestamp as number) ?? Date.now() / 1000,
            node: nodeId ?? null,
            message: (event.message as string) ?? (data.message as string) ?? '',
            level: (event.level as string) ?? 'info',
          })
          break

        case 'metric':
          if (nodeId) {
            state.appendMetric(
              runId,
              nodeId,
              (event.name as string) ?? (data.name as string) ?? '',
              (event.step as number) ?? (data.step as number) ?? 0,
              (event.value as number) ?? (data.value as number) ?? 0,
            )
          }
          break

        case 'progress':
          if (nodeId) {
            state.updateNodeProgress(runId, nodeId, data as { current: number; total: number })
          }
          break

        case 'error':
          state.appendRunError(runId, {
            timestamp: (data.timestamp as number) ?? Date.now() / 1000,
            node_name: (data.node as string) ?? nodeId ?? '',
            node_docstring: (data.docstring as string) ?? null,
            exception_type: (data.type as string) ?? '',
            exception_message: (data.error as string) ?? '',
            traceback: (data.traceback as string) ?? '',
            execution_count: (data.exec_count as number) ?? 0,
            params: (data.params as Record<string, unknown>) ?? {},
            last_logs: (data.last_logs as string[]) ?? [],
          })
          break

        case 'node_register':
          state.updateNodeRegistration(runId, data)
          break

        case 'node_executed': {
          const nid = (data.node_id as string) ?? nodeId ?? ''
          if (nid) state.incrementNodeExecution(runId, nid)
          const caller = data.caller as string | undefined
          if (caller && nid) state.addEdge(runId, caller, nid)
          break
        }

        case 'edge':
          state.addEdge(runId, (data.source as string) ?? '', (data.target as string) ?? '')
          break

        case 'inspection':
          if (nodeId) {
            state.updateInspection(runId, nodeId, (data.name as string) ?? 'unnamed', data)
          }
          break

        case 'description':
          state.setWorkflowDescription(runId, (data.description as string) ?? '')
          break

        case 'ask_prompt':
          state.addAskPrompt(runId, {
            askId: (data.ask_id as string) ?? `ask_${Date.now()}`,
            nodeName: (data.node_name as string) ?? nodeId ?? '',
            question: (data.question as string) ?? '',
            options: (data.options as string[]) ?? null,
            timeoutSeconds: (data.timeout_seconds as number) ?? null,
            receivedAt: new Date(),
          })
          break

        case 'run_start':
          set(st => {
            const runs = new Map(st.runs)
            const r = runs.get(runId)
            if (r) {
              const scriptPath = (data.script_path as string) ?? ''
              if (scriptPath) r.summary.script_path = scriptPath
            }
            return { runs }
          })
          break

        case 'run_completed':
          set(st => {
            const runs = new Map(st.runs)
            const r = runs.get(runId)
            if (r) {
              const exitCode = (data.exit_code as number) ?? 0
              r.summary.status = exitCode === 0 ? 'completed' : 'crashed'
              r.summary.exit_code = exitCode
              r.summary.ended_at = new Date().toISOString()
            }
            return { runs }
          })
          break
      }
    }
  },
}))
