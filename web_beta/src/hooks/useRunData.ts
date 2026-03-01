import { useEffect } from 'react'
import { useStore } from '@/store'
import { api } from '@/lib/api'

export function useRunData(runId: string | null) {
  const runs = useStore(s => s.runs)
  const setRunGraph = useStore(s => s.setRunGraph)
  const setRunLogs = useStore(s => s.setRunLogs)
  const setRunErrors = useStore(s => s.setRunErrors)

  const run = runId ? runs.get(runId) : undefined

  useEffect(() => {
    if (!runId || run?.loaded) return

    Promise.all([
      api.getRunGraph(runId).then(g => setRunGraph(runId, g)),
      api.getRunLogs(runId, { limit: 500 }).then(d => setRunLogs(runId, d.logs)),
      api.getRunErrors(runId).then(d => setRunErrors(runId, d.errors)),
    ]).catch(() => { /* Run may not exist yet */ })
  }, [runId, run?.loaded, setRunGraph, setRunLogs, setRunErrors])

  return run ?? null
}
