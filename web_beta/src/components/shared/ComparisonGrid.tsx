import type { ReactNode } from 'react'
import { useStore } from '@/store'
import { getGridDimensions } from '@/lib/grid'

interface ComparisonGridProps {
  runIds: string[]
  children: (runId: string, index: number) => ReactNode
}

export function ComparisonGrid({ runIds, children }: ComparisonGridProps) {
  const runColors = useStore(s => s.runColors)
  const runNames = useStore(s => s.runNames)
  const runs = useStore(s => s.runs)

  const { cols, rows } = getGridDimensions(runIds.length)
  const totalCells = cols * rows

  return (
    <div
      className="grid gap-px bg-border"
      style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
    >
      {Array.from({ length: totalCells }, (_, i) => {
        const runId = runIds[i]
        if (!runId) {
          return <div key={`empty-${i}`} className="bg-background" />
        }

        const color = runColors.get(runId) ?? '#60a5fa'
        const run = runs.get(runId)
        const scriptName = run?.summary.script_path.split('/').pop() ?? runId
        const displayName = runNames.get(runId) || scriptName

        return (
          <div key={runId} className="bg-background min-w-0 flex flex-col">
            <div
              className="flex items-center gap-1.5 px-2 py-1 border-b border-border shrink-0"
              style={{ borderTop: `3px solid ${color}` }}
            >
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] text-muted-foreground truncate">
                {displayName}
              </span>
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              {children(runId, i)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
