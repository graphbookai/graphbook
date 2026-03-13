import { useCallback, useMemo, useRef, useState } from 'react'
import { useStore } from '@/store'
import { useTimelineBounds, type TimelineEvent } from '@/hooks/useTimelineBounds'
import { Switch } from '@/components/ui/switch'

const DOT_COLORS: Record<TimelineEvent['type'], string> = {
  log: '#3b82f6',    // blue
  image: '#22c55e',  // green
  audio: '#f97316',  // orange
}

interface TimelineScrubberProps {
  runId: string
}

const EVENT_TYPES: TimelineEvent['type'][] = ['log', 'image', 'audio']

export function TimelineScrubber({ runId }: TimelineScrubberProps) {
  const bounds = useTimelineBounds(runId)
  const timeline = useStore(s => s.timeline)
  const setTimelineMode = useStore(s => s.setTimelineMode)
  const setTimeRange = useStore(s => s.setTimeRange)
  const setTimelineStep = useStore(s => s.setTimelineStep)

  const [dotFilters, setDotFilters] = useState<Set<TimelineEvent['type']>>(
    () => new Set(EVENT_TYPES)
  )

  const toggleFilter = useCallback((type: TimelineEvent['type']) => {
    setDotFilters(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }, [])

  const filteredEvents = useMemo(
    () => bounds.events.filter(ev => dotFilters.has(ev.type)),
    [bounds.events, dotFilters]
  )

  const isStepMode = timeline.mode === 'step'

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-t border-border bg-background shrink-0 h-14">
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
            events={filteredEvents}
          />
        ) : (
          <TimeRangeTrack
            minTime={bounds.minTime}
            maxTime={bounds.maxTime}
            startValue={timeline.timeStart}
            endValue={timeline.timeEnd}
            onChange={setTimeRange}
            events={filteredEvents}
          />
        )}
      </div>

      {/* Dot type filters */}
      <div className="flex items-center gap-2 shrink-0">
        {EVENT_TYPES.map(type => (
          <label key={type} className="flex items-center gap-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={dotFilters.has(type)}
              onChange={() => toggleFilter(type)}
              className="w-2.5 h-2.5 rounded-sm accent-current cursor-pointer"
              style={{ accentColor: DOT_COLORS[type] }}
            />
            <span className="text-[10px] text-muted-foreground capitalize">{type === 'log' ? 'Logs' : type === 'image' ? 'Images' : 'Audio'}</span>
          </label>
        ))}
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
  events: TimelineEvent[]
}

function TimeRangeTrack({ minTime, maxTime, startValue, endValue, onChange, events }: TimeRangeTrackProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState<'start' | 'end' | 'window' | 'pan' | null>(null)
  const dragStartX = useRef(0)
  const dragStartValues = useRef<{ start: number; end: number }>({ start: 0, end: 0 })
  const dragStartPanX = useRef(0)

  // Visual zoom state — does not change time range, only scales the track
  const [scale, setScale] = useState(1)
  const [panX, setPanX] = useState(0) // translateX in px for the inner track

  const range = maxTime - minTime
  const effectiveStart = startValue ?? minTime
  const effectiveEnd = endValue ?? maxTime

  const toPercent = (t: number) => (range > 0 ? ((t - minTime) / range) * 100 : 0)

  // Map screen pixel → time value, accounting for zoom transform
  const fromPixel = (px: number) => {
    if (!containerRef.current || range <= 0) return minTime
    const rect = containerRef.current.getBoundingClientRect()
    const containerW = rect.width
    const trackX = (px - rect.left - panX) / scale
    const frac = Math.max(0, Math.min(1, trackX / containerW))
    return minTime + frac * range
  }

  const clampPanX = useCallback((px: number, s: number) => {
    if (!containerRef.current || s <= 1) return 0
    const containerW = containerRef.current.getBoundingClientRect().width
    return Math.min(0, Math.max(containerW * (1 - s), px))
  }, [])

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

    if (dragging === 'pan') {
      const dx = e.clientX - dragStartX.current
      setPanX(clampPanX(dragStartPanX.current + dx, scale))
      return
    }

    const t = fromPixel(e.clientX)

    if (dragging === 'start') {
      onChange(Math.min(t, effectiveEnd), endValue ?? maxTime)
    } else if (dragging === 'end') {
      onChange(startValue ?? minTime, Math.max(t, effectiveStart))
    } else if (dragging === 'window' && containerRef.current) {
      const containerW = containerRef.current.getBoundingClientRect().width
      const scaledW = containerW * scale
      const dx = e.clientX - dragStartX.current
      const dtFrac = dx / scaledW
      const dt = dtFrac * range
      const windowSize = dragStartValues.current.end - dragStartValues.current.start
      let newStart = dragStartValues.current.start + dt
      let newEnd = dragStartValues.current.end + dt
      if (newStart < minTime) { newStart = minTime; newEnd = minTime + windowSize }
      if (newEnd > maxTime) { newEnd = maxTime; newStart = maxTime - windowSize }
      onChange(newStart, newEnd)
    }
  }, [dragging, effectiveStart, effectiveEnd, startValue, endValue, minTime, maxTime, range, scale, clampPanX, onChange, fromPixel])

  const handlePointerUp = useCallback(() => {
    setDragging(null)
  }, [])

  // Click-drag on empty space → pan the viewport
  const handleTrackPointerDown = useCallback((e: React.PointerEvent) => {
    if (dragging) return
    e.preventDefault()
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    setDragging('pan')
    dragStartX.current = e.clientX
    dragStartPanX.current = panX
  }, [dragging, panX])

  const handleDoubleClick = useCallback(() => {
    onChange(null, null)
    setScale(1)
    setPanX(0)
  }, [onChange])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    if (range <= 0 || !containerRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    const cursorX = e.clientX - rect.left // cursor position relative to container

    const zoomFactor = e.deltaY < 0 ? 1.25 : 1 / 1.25 // scroll up = zoom in
    const newScale = Math.max(1, Math.min(50, scale * zoomFactor))

    // Keep the point under cursor stable:
    // Before: screenX = trackPoint * scale + panX  →  trackPoint = (cursorX - panX) / scale
    // After:  cursorX = trackPoint * newScale + newPanX
    const trackPoint = (cursorX - panX) / scale
    let newPanX = cursorX - trackPoint * newScale

    // Clamp so track edges don't go past container edges
    // Left: panX <= 0, Right: panX >= containerW * (1 - newScale)
    const containerW = rect.width
    newPanX = Math.min(0, Math.max(containerW * (1 - newScale), newPanX))

    if (newScale <= 1) {
      setScale(1)
      setPanX(0)
    } else {
      setScale(newScale)
      setPanX(newPanX)
    }
  }, [range, scale, panX])

  const dots = useEventDots(events, (ev) => toPercent(ev.timestamp))

  if (range <= 0) {
    return <div className="text-[10px] text-muted-foreground">No time data</div>
  }

  return (
    <div className="relative flex items-center h-10">
      <div
        ref={containerRef}
        className="relative w-full h-6 bg-muted rounded-lg cursor-grab overflow-hidden active:cursor-grabbing"
        onPointerDown={handleTrackPointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
      >
        {/* Inner track — scaled and translated for zoom */}
        <div
          className="absolute top-0 h-full"
          style={{
            width: `${scale * 100}%`,
            transform: `translateX(${panX}px)`,
          }}
        >
          {/* Event dots layer */}
          <EventDotLayer dots={dots} />

          {/* Highlighted window */}
          <div
            className={`absolute top-0 h-full ${isActive ? 'bg-primary/30' : 'bg-primary/10'}`}
            style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
            onPointerDown={(e) => handlePointerDown(e, 'window')}
          />

          {/* Start handle */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-1 h-full bg-primary rounded-sm cursor-ew-resize hover:bg-primary/80"
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
            className="absolute top-1/2 -translate-y-1/2 w-1 h-full bg-primary rounded-sm cursor-ew-resize hover:bg-primary/80"
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
  events: TimelineEvent[]
}

function StepTrack({ minStep, maxStep, hasSteps, value, onChange, events }: StepTrackProps) {
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

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    if (range <= 0) return
    const current = value ?? Math.round((minStep + maxStep) / 2)
    const delta = e.deltaY > 0 ? 1 : -1
    const next = Math.max(minStep, Math.min(maxStep, current + delta))
    onChange(next)
  }, [range, value, minStep, maxStep, onChange])

  // Only show events that have a step value
  const stepEvents = useMemo(() => events.filter(ev => ev.step != null), [events])
  const dots = useEventDots(stepEvents, (ev) => toPercent(ev.step!))

  if (!hasSteps) {
    return <div className="text-[10px] text-muted-foreground opacity-50">No step data</div>
  }

  const currentPct = value != null ? toPercent(value) : 50

  return (
    <div className="relative flex items-center h-10">
      <div
        ref={trackRef}
        className="relative w-full h-6 bg-muted cursor-pointer"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
      >
        {/* Event dots layer */}
        <EventDotLayer dots={dots} />

        {/* Handle */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 w-1 h-full rounded-sm cursor-ew-resize ${
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

// --- Event Dots ---

interface MergedDot {
  pct: number
  count: number
  color: string
  title: string
}

function useEventDots(
  events: TimelineEvent[],
  toPercent: (ev: TimelineEvent) => number,
): MergedDot[] {
  return useMemo(() => {
    if (events.length === 0) return []

    // Bucket events by pixel proximity (~0.5% of track width)
    const bucketSize = 0.5
    const buckets = new Map<number, TimelineEvent[]>()

    for (const ev of events) {
      const pct = toPercent(ev)
      const key = Math.round(pct / bucketSize) * bucketSize
      const existing = buckets.get(key)
      if (existing) {
        existing.push(ev)
      } else {
        buckets.set(key, [ev])
      }
    }

    const dots: MergedDot[] = []
    for (const [pct, group] of buckets) {
      // Use color of the most common type in the group
      const typeCounts: Record<string, number> = {}
      for (const ev of group) {
        typeCounts[ev.type] = (typeCounts[ev.type] || 0) + 1
      }
      let dominantType: TimelineEvent['type'] = 'log'
      let maxCount = 0
      for (const [type, count] of Object.entries(typeCounts)) {
        if (count > maxCount) { maxCount = count; dominantType = type as TimelineEvent['type'] }
      }

      const title = group.length === 1
        ? group[0].label
        : `${group.length} events: ${group.slice(0, 3).map(e => e.label).join(', ')}${group.length > 3 ? '…' : ''}`

      dots.push({
        pct,
        count: group.length,
        color: DOT_COLORS[dominantType],
        title,
      })
    }

    return dots
  }, [events, toPercent])
}

function EventDotLayer({ dots }: { dots: MergedDot[] }) {
  if (dots.length === 0) return null

  return (
    <svg
      className="absolute inset-0 w-full h-full overflow-visible pointer-events-none"
      preserveAspectRatio="none"
    >
      {dots.map((dot, i) => {
        const r = dot.count > 1 ? Math.min(5, 2 + dot.count * 0.5) : 2
        return (
          <circle
            key={i}
            cx={`${dot.pct}%`}
            cy="50%"
            r={r}
            fill={dot.color}
            opacity={0.8}
            style={{ pointerEvents: 'auto' }}
          >
            <title>{dot.title}</title>
          </circle>
        )
      })}
    </svg>
  )
}
