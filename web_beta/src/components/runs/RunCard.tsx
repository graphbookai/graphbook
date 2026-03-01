import { cn } from '@/lib/utils'
import { timeSince } from '@/lib/utils'
import { RunStatusBadge } from './RunStatusBadge'
import type { RunSummary } from '@/lib/api'

interface RunCardProps {
  run: RunSummary
  selected: boolean
  onClick: () => void
}

export function RunCard({ run, selected, onClick }: RunCardProps) {
  const scriptName = run.script_path.split('/').pop() ?? run.script_path
  const startedAt = run.started_at ? new Date(run.started_at) : null
  const duration = startedAt ? timeSince(startedAt) : '—'

  const errorInfo = run.status === 'crashed' && run.error_count > 0
    ? `${run.error_count} error${run.error_count > 1 ? 's' : ''}`
    : null

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-4 py-3 rounded-lg transition-colors',
        'hover:bg-accent/50',
        selected && 'bg-accent border border-accent-foreground/10',
        !selected && 'border border-transparent',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <RunStatusBadge status={run.status} />
            <span className="text-sm font-medium truncate">{scriptName}</span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <span>{duration}</span>
            <span>·</span>
            <span>{run.node_count} node{run.node_count !== 1 ? 's' : ''}</span>
            {errorInfo && (
              <>
                <span>·</span>
                <span className="text-red-500">{errorInfo}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}
