import { create } from 'zustand'
import type { RunSummary, GraphData, LogEntry, ErrorEntry } from '@/lib/api'
import type { WsEvent } from '@/lib/ws'
import { assignColor } from '@/lib/colors'

export interface NodeState {
  name: string
  funcName: string
  docstring: string | null
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

export interface Settings {
  theme: 'dark' | 'light'
  showMinimap: boolean
  showControls: boolean
  collapseNodesByDefault: boolean
  hideTabsOnDrag: boolean
  hideUncalledFunctions: boolean
}

const SETTINGS_KEY = 'gb_settings'

const DEFAULT_SETTINGS: Settings = {
  theme: 'dark',
  showMinimap: true,
  showControls: true,
  collapseNodesByDefault: false,
  hideTabsOnDrag: false,
  hideUncalledFunctions: true,
}

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return { ...DEFAULT_SETTINGS, ...parsed }
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_SETTINGS }
}

function saveSettings(settings: Settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  } catch { /* ignore */ }
}

const initialSettings = loadSettings()

// Apply persisted theme on load
document.documentElement.classList.toggle('dark', initialSettings.theme === 'dark')

export type NodeTab = 'info' | 'logs' | 'metrics' | 'images' | 'audio' | 'ask'

export interface PinnedPanel {
  id: string
  runId: string
  nodeId: string
  tab: NodeTab
  title: string
}

export interface ImageEntry {
  node: string
  mediaId: string
  name: string
  step: number | null
  timestamp: number
}

export interface AudioEntry {
  node: string
  mediaId: string
  name: string
  sr: number
  step: number | null
  timestamp: number
}

export type TimelineMode = 'time' | 'step'

export interface TimelineState {
  mode: TimelineMode
  timeStart: number | null
  timeEnd: number | null
  step: number | null
}

export interface ComparisonGroup {
  id: string
  title: string
  runIds: string[]
  createdAt: Date
}

export interface RunState {
  summary: RunSummary
  graph: GraphData | null
  logs: LogEntry[]
  errors: ErrorEntry[]
  nodeMetrics: Record<string, Record<string, { step: number; value: number }[]>>
  nodeImages: Record<string, ImageEntry[]>
  nodeAudio: Record<string, AudioEntry[]>
  inspections: Record<string, Record<string, unknown>>
  pendingAsks: Map<string, AskPrompt>
  paused: boolean
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

  runNames: Map<string, string>  // client-side custom display names
  setRunName: (runId: string, name: string) => void

  runColors: Map<string, string>
  nextColorIndex: number
  setRunColor: (runId: string, color: string) => void
  getOrAssignRunColor: (runId: string) => string

  // Comparison
  selectedForCompare: Set<string>
  comparisonGroups: Map<string, ComparisonGroup>
  toggleSelectForCompare: (runId: string) => void
  createComparisonGroup: (runIds: string[]) => string
  removeComparisonGroup: (groupId: string) => void

  // Node interaction (graph view)
  collapsedGraphNodes: Set<string>
  layoutTrigger: number
  dagDirection: 'TB' | 'LR'
  toggleDagDirection: () => void

  // Pinned panels
  pinnedPanels: PinnedPanel[]

  // Node positions & sizes (per run, session-only)
  nodePositions: Map<string, Map<string, { x: number; y: number }>>
  nodeSizes: Map<string, Map<string, { width: number; height: number }>>
  resizingNodeId: string | null
  toggleNodeResize: (nodeId: string) => void
  updateNodeSize: (runId: string, nodeId: string, size: { width: number; height: number }) => void

  // Node list panel (desktop)
  nodeListCollapsed: boolean
  toggleNodeList: () => void

  // Desktop view mode
  desktopViewMode: 'graph' | 'grid'
  setDesktopViewMode: (mode: 'graph' | 'grid') => void

  // Timeline
  timeline: TimelineState
  setTimelineMode: (mode: TimelineMode) => void
  setTimeRange: (start: number | null, end: number | null) => void
  setTimelineStep: (step: number | null) => void

  // Settings
  settings: Settings

  // Actions
  setRuns: (summaries: RunSummary[], activeRunId: string | null) => void
  updateRunSummary: (summary: RunSummary) => void
  setRunGraph: (runId: string, graph: GraphData) => void
  setRunLogs: (runId: string, logs: LogEntry[]) => void
  appendRunLog: (runId: string, log: LogEntry) => void
  setRunErrors: (runId: string, errors: ErrorEntry[]) => void
  appendRunError: (runId: string, error: ErrorEntry) => void
  setRunMetrics: (runId: string, metrics: Record<string, Record<string, { step: number; value: number }[]>>) => void
  setRunImages: (runId: string, images: Record<string, ImageEntry[]>) => void
  setRunAudio: (runId: string, audio: Record<string, AudioEntry[]>) => void
  appendMetric: (runId: string, nodeId: string, name: string, step: number, value: number) => void
  updateNodeProgress: (runId: string, nodeId: string, progress: { current: number; total: number; name?: string } | null) => void
  updateNodeRegistration: (runId: string, data: Record<string, unknown>) => void
  incrementNodeExecution: (runId: string, nodeId: string) => void
  addEdge: (runId: string, source: string, target: string) => void
  updateInspection: (runId: string, nodeId: string, name: string, data: unknown) => void
  setWorkflowDescription: (runId: string, description: string) => void

  // Media cache (mediaId -> base64 data)
  mediaCache: Map<string, string>
  cacheMedia: (mediaId: string, data: string) => void

  selectRun: (runId: string | null) => void
  toggleGraphNode: (nodeId: string) => void
  collapseAllGraphNodes: () => void
  expandAllGraphNodes: () => void
  requestLayout: () => void
  pinTab: (runId: string, nodeId: string, tab: NodeTab) => void
  unpinPanel: (panelId: string) => void

  updateNodePosition: (runId: string, nodeId: string, pos: { x: number; y: number }) => void
  resetLayout: (runId: string) => void

  addAskPrompt: (runId: string, prompt: AskPrompt) => void
  removeAskPrompt: (runId: string, askId: string) => void
  setPaused: (runId: string, paused: boolean) => void

  updateSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void

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
      nodeImages: {},
      nodeAudio: {},
      inspections: {},
      pendingAsks: new Map(),
      paused: false,
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

  runNames: new Map(),
  setRunName: (runId, name) => set(state => {
    const next = new Map(state.runNames)
    if (name.trim()) {
      next.set(runId, name.trim())
    } else {
      next.delete(runId)
    }
    return { runNames: next }
  }),

  runColors: new Map(),
  nextColorIndex: 0,
  setRunColor: (runId, color) => set(state => {
    const next = new Map(state.runColors)
    next.set(runId, color)
    return { runColors: next }
  }),
  getOrAssignRunColor: (runId) => {
    const state = get()
    const existing = state.runColors.get(runId)
    if (existing) return existing
    const color = assignColor(state.nextColorIndex)
    const next = new Map(state.runColors)
    next.set(runId, color)
    set({ runColors: next, nextColorIndex: state.nextColorIndex + 1 })
    return color
  },

  selectedForCompare: new Set<string>(),
  comparisonGroups: new Map(),
  toggleSelectForCompare: (runId) => set(state => {
    const next = new Set(state.selectedForCompare)
    if (next.has(runId)) next.delete(runId)
    else next.add(runId)
    return { selectedForCompare: next }
  }),
  createComparisonGroup: (runIds) => {
    const id = `cmp:${Date.now()}`
    const state = get()
    const names = runIds.map(rid => {
      const custom = state.runNames.get(rid)
      if (custom) return custom
      const run = state.runs.get(rid)
      return run?.summary.script_path.split('/').pop() ?? rid
    })
    const title = names.length <= 2
      ? `Compare: ${names.join(' vs ')}`
      : `Compare: ${names[0]} vs ${names[1]} +${names.length - 2}`
    const group: ComparisonGroup = { id, title, runIds, createdAt: new Date() }
    const next = new Map(state.comparisonGroups)
    next.set(id, group)
    set({ comparisonGroups: next, selectedForCompare: new Set() })
    return id
  },
  removeComparisonGroup: (groupId) => set(state => {
    const next = new Map(state.comparisonGroups)
    next.delete(groupId)
    const updates: Partial<GraphbookStore> = { comparisonGroups: next }
    if (state.selectedRunId === groupId) updates.selectedRunId = null
    return updates
  }),

  collapsedGraphNodes: new Set<string>(),
  layoutTrigger: 0,
  dagDirection: 'TB',
  toggleDagDirection: () => set(state => ({
    dagDirection: state.dagDirection === 'TB' ? 'LR' : 'TB',
    layoutTrigger: state.layoutTrigger + 1,
  })),

  pinnedPanels: [],

  nodePositions: new Map(),
  nodeSizes: new Map(),
  resizingNodeId: null,
  toggleNodeResize: (nodeId) => set(state => ({
    resizingNodeId: state.resizingNodeId === nodeId ? null : nodeId,
  })),
  updateNodeSize: (runId, nodeId, size) => set(state => {
    const outer = new Map(state.nodeSizes)
    const inner = new Map(outer.get(runId) ?? [])
    inner.set(nodeId, size)
    outer.set(runId, inner)
    return { nodeSizes: outer }
  }),

  nodeListCollapsed: false,
  toggleNodeList: () => set(state => ({ nodeListCollapsed: !state.nodeListCollapsed })),

  desktopViewMode: 'graph' as const,
  setDesktopViewMode: (mode) => set({ desktopViewMode: mode }),

  timeline: { mode: 'time', timeStart: null, timeEnd: null, step: null },
  setTimelineMode: (mode) => set(state => ({ timeline: { ...state.timeline, mode } })),
  setTimeRange: (start, end) => set(state => ({ timeline: { ...state.timeline, timeStart: start, timeEnd: end } })),
  setTimelineStep: (step) => set(state => ({ timeline: { ...state.timeline, step } })),

  settings: initialSettings,

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
          nodeImages: {},
          nodeAudio: {},
          inspections: {},
          pendingAsks: new Map(),
          paused: false,
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
      run.paused = graph.paused ?? false
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

  setRunMetrics: (runId, metrics) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) run.nodeMetrics = metrics
    return { runs }
  }),

  setRunImages: (runId, images) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      const merged: Record<string, ImageEntry[]> = { ...run.nodeImages }
      for (const [nodeId, entries] of Object.entries(images)) {
        const existing = merged[nodeId] ?? []
        const existingIds = new Set(existing.map(e => e.mediaId))
        const newEntries = entries.filter(e => !existingIds.has(e.mediaId))
        merged[nodeId] = [...existing, ...newEntries]
      }
      run.nodeImages = merged
    }
    return { runs }
  }),

  setRunAudio: (runId, audio) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      const merged: Record<string, AudioEntry[]> = { ...run.nodeAudio }
      for (const [nodeId, entries] of Object.entries(audio)) {
        const existing = merged[nodeId] ?? []
        const existingIds = new Set(existing.map(e => e.mediaId))
        const newEntries = entries.filter(e => !existingIds.has(e.mediaId))
        merged[nodeId] = [...existing, ...newEntries]
      }
      run.nodeAudio = merged
    }
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
        run.graph = { nodes: {}, edges: [], workflow_description: null, has_pausable: false, paused: false }
      }
      if (!run.graph.nodes[nodeId]) {
        run.graph.nodes[nodeId] = {
          name: nodeId,
          func_name: (data.func_name as string) || '',
          docstring: (data.docstring as string) || null,
          exec_count: 0,
          is_source: true,
          pausable: false,
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

  // Media cache
  mediaCache: new Map(),
  cacheMedia: (mediaId, data) => set(state => {
    const next = new Map(state.mediaCache)
    next.set(mediaId, data)
    return { mediaCache: next }
  }),

  selectRun: (runId) => set({ selectedRunId: runId }),
  toggleGraphNode: (nodeId) => set(state => {
    const next = new Set(state.collapsedGraphNodes)
    if (next.has(nodeId)) {
      next.delete(nodeId)
    } else {
      next.add(nodeId)
    }
    return { collapsedGraphNodes: next, layoutTrigger: state.layoutTrigger + 1 }
  }),
  collapseAllGraphNodes: () => set(state => {
    const selectedRun = state.selectedRunId ? state.runs.get(state.selectedRunId) : null
    const allIds = selectedRun?.graph ? Object.keys(selectedRun.graph.nodes) : []
    return { collapsedGraphNodes: new Set(allIds), layoutTrigger: state.layoutTrigger + 1 }
  }),
  expandAllGraphNodes: () => set(state => ({ collapsedGraphNodes: new Set<string>(), layoutTrigger: state.layoutTrigger + 1 })),
  requestLayout: () => set(state => ({ layoutTrigger: state.layoutTrigger + 1 })),
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

  setPaused: (runId, paused) => set(state => {
    const runs = new Map(state.runs)
    const run = runs.get(runId)
    if (run) {
      run.paused = paused
    }
    return { runs }
  }),

  updateSetting: (key, value) => set(state => {
    const next = { ...state.settings, [key]: value }
    saveSettings(next)
    if (key === 'theme') {
      document.documentElement.classList.toggle('dark', next.theme === 'dark')
    }
    return { settings: next }
  }),

  processWsEvents: (runId, events) => {
    // Single batched set() — avoids N re-renders per WS batch
    set(state => {
      const runs = new Map(state.runs)

      // Ensure the run exists
      let run = runs.get(runId)
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
          nodeImages: {},
          nodeAudio: {},
          inspections: {},
          pendingAsks: new Map(),
          paused: false,
          loaded: false,
        }
      }
      // Clone run so selectors see a new reference
      run = { ...run }
      runs.set(runId, run)

      // Accumulate new logs/errors/collapsed so we can spread once at the end
      const newLogs: LogEntry[] = []
      const newErrors: ErrorEntry[] = []
      const newCollapsedIds: string[] = []

      for (const event of events) {
        const etype = event.type
        const nodeId = event.node as string | undefined
        const data = (event.data ?? event) as Record<string, unknown>

        switch (etype) {
          case 'log':
            newLogs.push({
              timestamp: (event.timestamp as number) ?? Date.now() / 1000,
              node: nodeId ?? null,
              message: (event.message as string) ?? (data.message as string) ?? '',
              level: (event.level as string) ?? 'info',
              step: (event.step as number) ?? null,
            })
            break

          case 'metric':
            if (nodeId) {
              const name = (event.name as string) ?? (data.name as string) ?? ''
              const step = (event.step as number) ?? (data.step as number) ?? 0
              const value = (event.value as number) ?? (data.value as number) ?? 0
              if (!run.nodeMetrics[nodeId]) run.nodeMetrics[nodeId] = {}
              if (!run.nodeMetrics[nodeId][name]) run.nodeMetrics[nodeId][name] = []
              run.nodeMetrics[nodeId][name] = [...run.nodeMetrics[nodeId][name], { step, value }]
            }
            break

          case 'progress':
            if (nodeId && run.graph?.nodes[nodeId]) {
              // New node object so primitive selectors detect the change; graph ref stays stable
              run.graph.nodes[nodeId] = {
                ...run.graph.nodes[nodeId],
                progress: data as { current: number; total: number; name?: string },
              }
            }
            break

          case 'error':
            newErrors.push({
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

          case 'node_register': {
            const nid = (data.node_id as string) || ''
            if (!run.graph) {
              run.graph = { nodes: {}, edges: [], workflow_description: null, has_pausable: false, paused: false }
            }
            const isPausable = !!(data.pausable as boolean)
            if (!run.graph.nodes[nid]) {
              // Structural change — new graph object
              run.graph = {
                ...run.graph,
                has_pausable: run.graph.has_pausable || isPausable,
                nodes: {
                  ...run.graph.nodes,
                  [nid]: {
                    name: nid,
                    func_name: (data.func_name as string) || '',
                    docstring: (data.docstring as string) || null,
                    exec_count: 0,
                    is_source: true,
                    pausable: isPausable,
                    params: {},
                    progress: null,
                  },
                },
              }
              run.summary.node_count = Object.keys(run.graph.nodes).length
              if (state.settings.collapseNodesByDefault) {
                newCollapsedIds.push(nid)
              }
            }
            break
          }

          case 'node_executed': {
            const nid = (data.node_id as string) ?? nodeId ?? ''
            if (nid && run.graph?.nodes[nid]) {
              // New node object for selector detection; graph ref stays stable
              run.graph.nodes[nid] = {
                ...run.graph.nodes[nid],
                exec_count: run.graph.nodes[nid].exec_count + 1,
              }
            }
            const caller = data.caller as string | undefined
            if (caller && nid && run.graph) {
              const exists = run.graph.edges.some(e => e.source === caller && e.target === nid)
              if (!exists) {
                // Structural change — new graph object
                run.graph = {
                  ...run.graph,
                  edges: [...run.graph.edges, { source: caller, target: nid }],
                  nodes: {
                    ...run.graph.nodes,
                    ...(run.graph.nodes[nid] ? {
                      [nid]: { ...run.graph.nodes[nid], is_source: false },
                    } : {}),
                  },
                }
                run.summary.edge_count = run.graph.edges.length
              }
            }
            break
          }

          case 'edge': {
            const source = (data.source as string) ?? ''
            const target = (data.target as string) ?? ''
            if (run.graph) {
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
            break
          }

          case 'image':
            if (nodeId) {
              const ev = event as Record<string, unknown>
              const prev = run.nodeImages[nodeId] ?? []
              run.nodeImages = { ...run.nodeImages, [nodeId]: [...prev, {
                node: nodeId,
                mediaId: (ev.media_id as string) ?? '',
                name: (ev.name as string) ?? '',
                step: (ev.step as number) ?? null,
                timestamp: (ev.timestamp as number) ?? Date.now() / 1000,
              }] }
            }
            break

          case 'audio':
            if (nodeId) {
              const ev = event as Record<string, unknown>
              const prev = run.nodeAudio[nodeId] ?? []
              run.nodeAudio = { ...run.nodeAudio, [nodeId]: [...prev, {
                node: nodeId,
                mediaId: (ev.media_id as string) ?? '',
                name: (ev.name as string) ?? '',
                sr: (ev.sr as number) ?? 16000,
                step: (ev.step as number) ?? null,
                timestamp: (ev.timestamp as number) ?? Date.now() / 1000,
              }] }
            }
            break

          case 'text':
            newLogs.push({
              timestamp: (event.timestamp as number) ?? Date.now() / 1000,
              node: nodeId ?? null,
              message: `[${(data.name as string) ?? ''}] ${(data.content as string) ?? (event.content as unknown as string) ?? ''}`,
              level: 'info',
              step: (event.step as number) ?? null,
            })
            break

          case 'inspection':
            if (nodeId) {
              if (!run.inspections[nodeId]) run.inspections[nodeId] = {}
              run.inspections[nodeId] = { ...run.inspections[nodeId], [(data.name as string) ?? 'unnamed']: data }
            }
            break

          case 'config':
            if (nodeId && run.graph?.nodes[nodeId]) {
              run.graph.nodes[nodeId] = {
                ...run.graph.nodes[nodeId],
                params: { ...run.graph.nodes[nodeId].params, ...(data as Record<string, unknown>) },
              }
            }
            break

          case 'description':
            if (run.graph) {
              run.graph = { ...run.graph, workflow_description: (data.description as string) ?? '' }
            }
            break

          case 'ask_prompt': {
            const asks = new Map(run.pendingAsks)
            const askId = (data.ask_id as string) ?? `ask_${Date.now()}`
            asks.set(askId, {
              askId,
              nodeName: (data.node_name as string) ?? nodeId ?? '',
              question: (data.question as string) ?? '',
              options: (data.options as string[]) ?? null,
              timeoutSeconds: (data.timeout_seconds as number) ?? null,
              receivedAt: new Date(),
            })
            run.pendingAsks = asks
            break
          }

          case 'run_start': {
            const scriptPath = (data.script_path as string) ?? ''
            if (scriptPath) {
              run.summary = { ...run.summary, script_path: scriptPath }
            }
            break
          }

          case 'run_completed': {
            const exitCode = (data.exit_code as number) ?? 0
            run.summary = {
              ...run.summary,
              status: exitCode === 0 ? 'completed' : 'crashed',
              exit_code: exitCode,
              ended_at: new Date().toISOString(),
            }
            break
          }

          case 'pause_state': {
            const paused = !!(data.paused as boolean)
            run.paused = paused
            if (run.graph) {
              run.graph = { ...run.graph, paused }
            }
            break
          }
        }
      }

      // Batch-append accumulated logs and errors
      if (newLogs.length > 0) {
        run.logs = [...run.logs, ...newLogs]
      }
      if (newErrors.length > 0) {
        run.errors = [...run.errors, ...newErrors]
      }

      // Collapse newly registered nodes if setting is enabled
      if (newCollapsedIds.length > 0) {
        const next = new Set(state.collapsedGraphNodes)
        for (const id of newCollapsedIds) next.add(id)
        return { runs, collapsedGraphNodes: next }
      }

      return { runs }
    })
  },
}))
