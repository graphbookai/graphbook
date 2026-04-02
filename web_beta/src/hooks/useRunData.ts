import { useEffect, useRef } from 'react'
import { useStore, type RunState } from '@/store'
import { api } from '@/lib/api'

function fetchSingleRun(runId: string, store: ReturnType<typeof useStore.getState>) {
  const { setRunGraph, setRunLogs, setRunErrors, setRunMetrics, setRunImages, setRunAudio, addAskPrompt } = store
  return Promise.all([
    api.getRunGraph(runId).then(g => setRunGraph(runId, g)),
    api.getRunLogs(runId, { limit: 500 }).then(d => setRunLogs(runId, d.logs)),
    api.getRunErrors(runId).then(d => setRunErrors(runId, d.errors)),
    api.getRunMetrics(runId).then(d => setRunMetrics(runId, d.metrics)),
    api.getRunImages(runId).then(d => {
      const mapped: Record<string, Array<{ node: string; mediaId: string; name: string; step: number | null; timestamp: number }>> = {}
      for (const [nodeId, entries] of Object.entries(d.images)) {
        mapped[nodeId] = entries.map(e => ({ node: e.node, mediaId: e.media_id, name: e.name, step: e.step, timestamp: e.timestamp }))
      }
      setRunImages(runId, mapped)
    }),
    api.getRunAudio(runId).then(d => {
      const mapped: Record<string, Array<{ node: string; mediaId: string; name: string; sr: number; step: number | null; timestamp: number }>> = {}
      for (const [nodeId, entries] of Object.entries(d.audio)) {
        mapped[nodeId] = entries.map(e => ({ node: e.node, mediaId: e.media_id, name: e.name, sr: e.sr, step: e.step, timestamp: e.timestamp }))
      }
      setRunAudio(runId, mapped)
    }),
    api.getRunAsks(runId).then(d => {
      for (const ask of d.pending) {
        addAskPrompt(runId, {
          askId: ask.ask_id,
          nodeName: ask.node_name ?? ask.node ?? '',
          question: ask.question ?? '',
          options: ask.options ?? null,
          timeoutSeconds: ask.timeout_seconds ?? null,
          receivedAt: new Date(),
        })
      }
    }),
  ]).catch((err) => { console.warn(`[useRunData] Failed to fetch data for run ${runId}:`, err) })
}

export function useRunData(runId: string | null): RunState | null {
  const runs = useStore(s => s.runs)
  const comparisonGroups = useStore(s => s.comparisonGroups)
  const fetchedRef = useRef(new Set<string>())

  const isComparison = runId?.startsWith('cmp:') ?? false
  const group = isComparison && runId ? comparisonGroups.get(runId) : null
  const run = runId && !isComparison ? runs.get(runId) : undefined

  // Fetch data for a single run
  useEffect(() => {
    if (!runId || isComparison || run?.loaded || fetchedRef.current.has(runId)) return
    fetchedRef.current.add(runId)
    fetchSingleRun(runId, useStore.getState())
  }, [runId, isComparison, run?.loaded])

  // Fetch data for all runs in a comparison group
  useEffect(() => {
    if (!group) return
    for (const rid of group.runIds) {
      const r = runs.get(rid)
      if (!r?.loaded && !fetchedRef.current.has(rid)) {
        fetchedRef.current.add(rid)
        fetchSingleRun(rid, useStore.getState())
      }
    }
  }, [group, runs])

  return run ?? null
}
