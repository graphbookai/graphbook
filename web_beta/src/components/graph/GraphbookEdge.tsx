import { memo } from 'react'
import { getBezierPath, type EdgeProps } from '@xyflow/react'
import { useStore } from '@/store'

export const GraphbookEdge = memo(function GraphbookEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps) {
  const runId = (data as { runId?: string })?.runId
  const run = runId ? useStore.getState().runs.get(runId) : undefined
  const isRunning = run?.summary.status === 'running'

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })

  return (
    <>
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke="oklch(0.556 0 0)"
        strokeWidth={2}
        strokeDasharray={isRunning ? '6 4' : undefined}
        className={isRunning ? 'animate-[dash_1s_linear_infinite]' : ''}
      />
      <style>{`
        @keyframes dash {
          to { stroke-dashoffset: -20; }
        }
      `}</style>
    </>
  )
})
