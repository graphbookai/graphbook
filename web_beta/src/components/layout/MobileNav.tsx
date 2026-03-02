import { useStore } from '@/store'
import { useRunDuration } from '@/hooks/useRunDuration'
import { SettingsPanel } from './SettingsPanel'
import { ArrowLeft, Wifi, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RunStatusBadge } from '@/components/runs/RunStatusBadge'

export function MobileNav() {
  const selectedRunId = useStore(s => s.selectedRunId)
  const runs = useStore(s => s.runs)
  const selectRun = useStore(s => s.selectRun)
  const connected = useStore(s => s.connected)

  const run = selectedRunId ? runs.get(selectedRunId) : null
  const duration = useRunDuration(run?.summary)

  if (run) {
    const scriptName = run.summary.script_path.split('/').pop() ?? run.summary.script_path

    return (
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-background">
        <Button variant="ghost" size="icon" onClick={() => selectRun(null)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium truncate">{scriptName}</span>
            <RunStatusBadge status={run.summary.status} />
          </div>
          <span className="text-xs text-muted-foreground">{duration}</span>
        </div>
        <div className="flex items-center gap-1">
          {connected ? (
            <Wifi className="h-4 w-4 text-green-500" />
          ) : (
            <WifiOff className="h-4 w-4 text-muted-foreground" />
          )}
          <SettingsPanel />
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background">
      <h1 className="text-lg font-semibold">Graphbook</h1>
      <div className="flex items-center gap-1">
        {connected ? (
          <Wifi className="h-4 w-4 text-green-500" />
        ) : (
          <WifiOff className="h-4 w-4 text-muted-foreground" />
        )}
        <SettingsPanel />
      </div>
    </div>
  )
}
