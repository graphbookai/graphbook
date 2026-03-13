import { useEffect } from 'react'
import { useStore } from '@/store'
import { api } from '@/lib/api'

export function useRunData(runId: string | null) {
  const runs = useStore(s => s.runs)
  const setRunGraph = useStore(s => s.setRunGraph)
  const setRunLogs = useStore(s => s.setRunLogs)
  const setRunErrors = useStore(s => s.setRunErrors)
  const setRunMetrics = useStore(s => s.setRunMetrics)
  const addAskPrompt = useStore(s => s.addAskPrompt)

  const run = runId ? runs.get(runId) : undefined

  useEffect(() => {
    if (!runId || run?.loaded) return

    Promise.all([
      api.getRunGraph(runId).then(g => setRunGraph(runId, g)),
      api.getRunLogs(runId, { limit: 500 }).then(d => setRunLogs(runId, d.logs)),
      api.getRunErrors(runId).then(d => setRunErrors(runId, d.errors)),
      api.getRunMetrics(runId).then(d => setRunMetrics(runId, d.metrics)),
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
    ]).catch(() => { /* Run may not exist yet */ })
  }, [runId, run?.loaded, setRunGraph, setRunLogs, setRunErrors, setRunMetrics, addAskPrompt])

  return run ?? null
}
