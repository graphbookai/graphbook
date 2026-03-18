import { useCallback, useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { useRunDuration } from '@/hooks/useRunDuration'
import { useStore } from '@/store'
import { RunStatusBadge } from './RunStatusBadge'
import type { RunSummary } from '@/lib/api'

interface RunCardProps {
  run: RunSummary
  selected: boolean
  onClick: () => void
}

export function RunCard({ run, selected, onClick }: RunCardProps) {
  const scriptName = run.script_path.split('/').pop() ?? run.script_path
  const customName = useStore(s => s.runNames.get(run.id))
  const setRunName = useStore(s => s.setRunName)
  const duration = useRunDuration(run)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const displayName = customName || scriptName

  const startEditing = useCallback(() => {
    setDraft(displayName)
    setEditing(true)
  }, [displayName])

  const commitEdit = useCallback(() => {
    setEditing(false)
    const trimmed = draft.trim()
    if (trimmed && trimmed !== scriptName) {
      setRunName(run.id, trimmed)
    } else if (!trimmed || trimmed === scriptName) {
      setRunName(run.id, '') // clear custom name, revert to default
    }
  }, [draft, scriptName, run.id, setRunName])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const startedAt = run.started_at
    ? new Date(run.started_at).toLocaleString(undefined, {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
      })
    : null

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
          {editing ? (
            <input
              ref={inputRef}
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={e => {
                if (e.key === 'Enter') commitEdit()
                if (e.key === 'Escape') setEditing(false)
              }}
              onClick={e => e.stopPropagation()}
              className="w-full text-sm font-medium bg-background border border-border rounded px-1 py-0 outline-none focus:ring-1 focus:ring-ring"
            />
          ) : (
            <div
              className="text-sm font-medium truncate cursor-text"
              onDoubleClick={(e) => { e.stopPropagation(); startEditing() }}
              title="Double-click to rename"
            >
              {displayName}
            </div>
          )}
          {startedAt && <div className="text-xs text-muted-foreground mt-0.5">{startedAt}</div>}
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
