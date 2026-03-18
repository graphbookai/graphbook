import { useCallback, useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { useStore, type ComparisonGroup } from '@/store'
import { Scale, X } from 'lucide-react'

interface ComparisonGroupCardProps {
  group: ComparisonGroup
  selected: boolean
  onClick: () => void
}

export function ComparisonGroupCard({ group, selected, onClick }: ComparisonGroupCardProps) {
  const runColors = useStore(s => s.runColors)
  const runNames = useStore(s => s.runNames)
  const runs = useStore(s => s.runs)
  const removeComparisonGroup = useStore(s => s.removeComparisonGroup)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // We store title edits in the comparison group itself
  // For now, use local state since the store doesn't have updateComparisonGroupTitle yet
  const [localTitle, setLocalTitle] = useState(group.title)

  const displayTitle = localTitle || group.title

  const startEditing = useCallback(() => {
    setDraft(displayTitle)
    setEditing(true)
  }, [displayTitle])

  const commitEdit = useCallback(() => {
    setEditing(false)
    const trimmed = draft.trim()
    if (trimmed) setLocalTitle(trimmed)
  }, [draft])

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const runDisplayNames = group.runIds.map(rid => {
    const custom = runNames.get(rid)
    if (custom) return { name: custom, color: runColors.get(rid) ?? '#60a5fa' }
    const run = runs.get(rid)
    const scriptName = run?.summary.script_path.split('/').pop() ?? rid
    return { name: scriptName, color: runColors.get(rid) ?? '#60a5fa' }
  })

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
            <Scale className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
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
                className="flex-1 text-sm font-medium bg-background border border-border rounded px-1 py-0 outline-none focus:ring-1 focus:ring-ring"
              />
            ) : (
              <span
                className="text-sm font-medium truncate flex-1 cursor-text"
                onDoubleClick={(e) => { e.stopPropagation(); startEditing() }}
                title="Double-click to rename"
              >
                {displayTitle}
              </span>
            )}
            <button
              className="shrink-0 p-0.5 rounded hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-colors"
              onClick={(e) => { e.stopPropagation(); removeComparisonGroup(group.id) }}
              title="Remove comparison"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Run names with colored dots */}
          <div
            className="flex items-center gap-2 mt-1 text-xs text-muted-foreground truncate"
            title={runDisplayNames.map(r => r.name).join('\n')}
          >
            {runDisplayNames.map((r, i) => (
              <span key={i} className="flex items-center gap-1 shrink-0">
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ backgroundColor: r.color }}
                />
                <span className="truncate max-w-[80px]">{r.name}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </button>
  )
}
