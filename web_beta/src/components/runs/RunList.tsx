import { useStore } from '@/store'
import { RunCard } from './RunCard'
import { ScrollArea } from '@/components/ui/scroll-area'

export function RunList() {
  const runs = useStore(s => s.runs)
  const selectedRunId = useStore(s => s.selectedRunId)
  const selectRun = useStore(s => s.selectRun)

  // Sort: running first, then by started_at descending
  const sortedRuns = Array.from(runs.values()).sort((a, b) => {
    const aRunning = a.summary.status === 'running' || a.summary.status === 'starting'
    const bRunning = b.summary.status === 'running' || b.summary.status === 'starting'
    if (aRunning && !bRunning) return -1
    if (!aRunning && bRunning) return 1
    const aTime = a.summary.started_at ? new Date(a.summary.started_at).getTime() : 0
    const bTime = b.summary.started_at ? new Date(b.summary.started_at).getTime() : 0
    return bTime - aTime
  })

  if (sortedRuns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-6">
        <p className="text-sm">No runs yet</p>
        <p className="text-xs mt-1">Start a pipeline with <code className="text-xs bg-muted px-1 py-0.5 rounded">graphbook run</code></p>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full [&>div>div]:!block">
      <div className="p-2 space-y-1">
        {sortedRuns.map(run => (
          <RunCard
            key={run.summary.id}
            run={run.summary}
            selected={run.summary.id === selectedRunId}
            onClick={() => selectRun(run.summary.id)}
          />
        ))}
      </div>
    </ScrollArea>
  )
}
