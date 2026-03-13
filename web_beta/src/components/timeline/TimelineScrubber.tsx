import { useCallback, useRef, useState } from 'react'
import { useStore } from '@/store'
import { useTimelineBounds } from '@/hooks/useTimelineBounds'
import { Switch } from '@/components/ui/switch'

interface TimelineScrubberProps {
  runId: string
}

export function TimelineScrubber({ runId }: TimelineScrubberProps) {
  const bounds = useTimelineBounds(runId)
  const timeline = useStore(s => s.timeline)
  const setTimelineMode = useStore(s => s.setTimelineMode)
  const setTimeRange = useStore(s => s.setTimeRange)
  const setTimelineStep = useStore(s => s.setTimelineStep)

  const isStepMode = timeline.mode === 'step'

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 border-t border-border bg-background shrink-0 h-10">
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-[10px] text-muted-foreground">Time</span>
        <Switch
          checked={isStepMode}
          onCheckedChange={(checked) => setTimelineMode(checked ? 'step' : 'time')}
          className="scale-75"
        />
        <span className="text-[10px] text-muted-foreground">Step</span>
      </div>

      <div className="flex-1 min-w-0">
        {isStepMode ? (
          <StepTrack
            minStep={bounds.minStep}
            maxStep={bounds.maxStep}
            hasSteps={bounds.hasSteps}
            value={timeline.step}
            onChange={setTimelineStep}
          />
        ) : (
          <TimeRangeTrack
            minTime={bounds.minTime}
            maxTime={bounds.maxTime}
            startValue={timeline.timeStart}
            endValue={timeline.timeEnd}
            onChange={setTimeRange}
          />
        )}
      </div>
    </div>
  )
}

// --- Time Range Track ---

interface TimeRangeTrackProps {
  minTime: number
  maxTime: number
  startValue: number | null
  endValue: number | null
  onChange: (start: number | null, end: number | null) => void
}

function TimeRangeTrack({ minTime, maxTime, startValue, endValue, onChange }: TimeRangeTrackProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState<'start' | 'end' | 'window' | null>(null)
  const dragStartX = useRef(0)
  const dragStartValues = useRef<{ start: number; end: number }>({ start: 0, end: 0 })

  const range = maxTime - minTime
  const effectiveStart = startValue ?? minTime
  const effectiveEnd = endValue ?? maxTime

  const toPercent = (t: number) => (range > 0 ? ((t - minTime) / range) * 100 : 0)
  const fromPixel = (px: number) => {
    if (!trackRef.current || range <= 0) return minTime
    const rect = trackRef.current.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (px - rect.left) / rect.width))
    return minTime + frac * range
  }

  const startPct = toPercent(effectiveStart)
  const endPct = toPercent(effectiveEnd)

  const formatOffset = (t: number) => {
    const offset = t - minTime
    if (offset < 60) return `${offset.toFixed(1)}s`
    return `${(offset / 60).toFixed(1)}m`
  }

  const isActive = startValue != null || endValue != null

  const handlePointerDown = useCallback((e: React.PointerEvent, target: 'start' | 'end' | 'window') => {
    e.preventDefault()
    e.stopPropagation()
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    setDragging(target)
    dragStartX.current = e.clientX
    dragStartValues.current = { start: effectiveStart, end: effectiveEnd }
  }, [effectiveStart, effectiveEnd])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return
    const t = fromPixel(e.clientX)

    if (dragging === 'start') {
      onChange(Math.min(t, effectiveEnd), endValue ?? maxTime)
    } else if (dragging === 'end') {
      onChange(startValue ?? minTime, Math.max(t, effectiveStart))
    } else if (dragging === 'window' && trackRef.current) {
      const rect = trackRef.current.getBoundingClientRect()
      const dx = e.clientX - dragStartX.current
      const dtFrac = dx / rect.width
      const dt = dtFrac * range
      const windowSize = dragStartValues.current.end - dragStartValues.current.start
      let newStart = dragStartValues.current.start + dt
      let newEnd = dragStartValues.current.end + dt
      if (newStart < minTime) { newStart = minTime; newEnd = minTime + windowSize }
      if (newEnd > maxTime) { newEnd = maxTime; newStart = maxTime - windowSize }
      onChange(newStart, newEnd)
    }
  }, [dragging, effectiveStart, effectiveEnd, startValue, endValue, minTime, maxTime, range, onChange, fromPixel])

  const handlePointerUp = useCallback(() => {
    setDragging(null)
  }, [])

  const handleTrackClick = useCallback((e: React.PointerEvent) => {
    if (dragging) return
    const t = fromPixel(e.clientX)
    // Set a 10-second window centered on click
    const halfWindow = Math.min(5, range / 2)
    onChange(Math.max(minTime, t - halfWindow), Math.min(maxTime, t + halfWindow))
  }, [dragging, fromPixel, range, minTime, maxTime, onChange])

  const handleDoubleClick = useCallback(() => {
    onChange(null, null)
  }, [onChange])

  if (range <= 0) {
    return <div className="text-[10px] text-muted-foreground">No time data</div>
  }

  return (
    <div className="relative flex items-center h-6">
      <div
        ref={trackRef}
        className="relative w-full h-2 bg-muted rounded-full cursor-pointer"
        onPointerDown={handleTrackClick}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
      >
        {/* Highlighted window */}
        <div
          className={`absolute top-0 h-full rounded-full ${isActive ? 'bg-primary/30' : 'bg-primary/10'}`}
          style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
          onPointerDown={(e) => handlePointerDown(e, 'window')}
        />

        {/* Start handle */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-4 bg-primary rounded-sm cursor-ew-resize -ml-1.5 hover:bg-primary/80"
          style={{ left: `${startPct}%` }}
          onPointerDown={(e) => handlePointerDown(e, 'start')}
        >
          {isActive && (
            <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-muted-foreground whitespace-nowrap">
              {formatOffset(effectiveStart)}
            </span>
          )}
        </div>

        {/* End handle */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-4 bg-primary rounded-sm cursor-ew-resize -ml-1.5 hover:bg-primary/80"
          style={{ left: `${endPct}%` }}
          onPointerDown={(e) => handlePointerDown(e, 'end')}
        >
          {isActive && (
            <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-muted-foreground whitespace-nowrap">
              {formatOffset(effectiveEnd)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Step Track ---

interface StepTrackProps {
  minStep: number
  maxStep: number
  hasSteps: boolean
  value: number | null
  onChange: (step: number | null) => void
}

function StepTrack({ minStep, maxStep, hasSteps, value, onChange }: StepTrackProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)

  const range = maxStep - minStep

  const fromPixel = useCallback((px: number) => {
    if (!trackRef.current || range <= 0) return minStep
    const rect = trackRef.current.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (px - rect.left) / rect.width))
    return Math.round(minStep + frac * range)
  }, [minStep, range])

  const toPercent = (s: number) => (range > 0 ? ((s - minStep) / range) * 100 : 50)

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    setDragging(true)
    onChange(fromPixel(e.clientX))
  }, [fromPixel, onChange])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return
    onChange(fromPixel(e.clientX))
  }, [dragging, fromPixel, onChange])

  const handlePointerUp = useCallback(() => {
    setDragging(false)
  }, [])

  const handleDoubleClick = useCallback(() => {
    onChange(null)
  }, [onChange])

  if (!hasSteps) {
    return <div className="text-[10px] text-muted-foreground opacity-50">No step data</div>
  }

  const currentPct = value != null ? toPercent(value) : 50

  return (
    <div className="relative flex items-center h-6">
      <div
        ref={trackRef}
        className="relative w-full h-2 bg-muted rounded-full cursor-pointer"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
      >
        {/* Handle */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 w-3 h-4 rounded-sm cursor-ew-resize -ml-1.5 ${
            value != null ? 'bg-primary hover:bg-primary/80' : 'bg-muted-foreground/40'
          }`}
          style={{ left: `${currentPct}%` }}
        >
          {value != null && (
            <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-muted-foreground whitespace-nowrap">
              step {value}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
