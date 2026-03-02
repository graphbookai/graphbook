import { cn } from '@/lib/utils'
import { useRunDuration } from '@/hooks/useRunDuration'
import { RunStatusBadge } from './RunStatusBadge'
import type { RunSummary } from '@/lib/api'

interface RunCardProps {
  run: RunSummary
  selected: boolean
  onClick: () => void
}

export function RunCard({ run, selected, onClick }: RunCardProps) {
  const scriptName = run.script_path.split('/').pop() ?? run.script_path
  const duration = useRunDuration(run)

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
          <div className="text-sm font-medium truncate">{scriptName}</div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex gap-2 text-xs text-muted-foreground">
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
            <RunStatusBadge status={run.status} />
          </div>
        </div>
      </div>
    </button>
  )
}
