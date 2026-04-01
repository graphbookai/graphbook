import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useStore } from '@/store'
import { useTimelineBounds, type TimelineEvent } from '@/hooks/useTimelineBounds'
import { Switch } from '@/components/ui/switch'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const DOT_COLORS: Record<TimelineEvent['type'], string> = {
  log: '#3b82f6',    // blue
  image: '#22c55e',  // green
  audio: '#f97316',  // orange
}

const DOT_MARGIN = 8 // px margin so dots don't touch edges (time track)
const STEP_TRACK_PAD = 12 // px padding so step dots/ticks don't touch edge marks

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
    <div className="flex items-center gap-3 px-4 py-2 border-t border-border bg-background shrink-0 h-24">
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-[10px] text-muted-foreground">Time</span>
        <Switch
          checked={isStepMode}
          onCheckedChange={(checked) => {
            setTimelineMode(checked ? 'step' : 'time')
            if (checked) setTimelineStep(bounds.minStep)
          }}
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

// --- Tick generation ---

function generateTicks(min: number, max: number, targetCount: number = 8): number[] {
  const range = max - min
  if (range <= 0) return []
  const rawStep = range / targetCount
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const norm = rawStep / mag
  let niceStep: number
  if (norm <= 1.5) niceStep = mag
  else if (norm <= 3.5) niceStep = 2 * mag
  else if (norm <= 7.5) niceStep = 5 * mag
  else niceStep = 10 * mag

  const ticks: number[] = []
  let t = Math.ceil(min / niceStep) * niceStep
  while (t <= max + niceStep * 0.001) {
    ticks.push(t)
    t += niceStep
  }
  return ticks
}

function formatTimeOffset(t: number, minTime: number): string {
  const offset = t - minTime
  if (offset < 60) return `${offset.toFixed(4)}s`
  return `${(offset / 60).toFixed(1)}m`
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

  const [scale, setScale] = useState(1)
  const [panX, setPanX] = useState(0)

  const range = maxTime - minTime
  const effectiveStart = startValue ?? minTime
  const effectiveEnd = endValue ?? maxTime

  const toPercent = (t: number) => (range > 0 ? ((t - minTime) / range) * 100 : 0)

  const fromPixel = (px: number) => {
    if (!containerRef.current || range <= 0) return minTime
    const rect = containerRef.current.getBoundingClientRect()
    const trackX = (px - rect.left - panX) / scale
    const frac = Math.max(0, Math.min(1, trackX / rect.width))
    return minTime + frac * range
  }

  const clampPanX = useCallback((px: number, s: number) => {
    if (!containerRef.current || s <= 1) return 0
    const containerW = containerRef.current.getBoundingClientRect().width
    return Math.min(0, Math.max(containerW * (1 - s), px))
  }, [])

  const startPct = toPercent(effectiveStart)
  const endPct = toPercent(effectiveEnd)

  const isActive = startValue != null || endValue != null
  const isDraggingWindow = dragging === 'start' || dragging === 'end' || dragging === 'window'

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
    const cursorX = e.clientX - rect.left

    const zoomFactor = e.deltaY < 0 ? 1.25 : 1 / 1.25
    const newScale = Math.max(1, Math.min(50, scale * zoomFactor))

    const trackPoint = (cursorX - panX) / scale
    let newPanX = cursorX - trackPoint * newScale

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

  const cw = containerRef.current?.clientWidth ?? 300
  const minPct = (-panX / (cw * scale)) * 100
  const maxPct = minPct + 100 / scale
  const visibleRange = useMemo<[number, number]>(() => [minPct - 2, maxPct + 2], [minPct, maxPct])
  const dots = useEventDots(events, (ev) => toPercent(ev.timestamp), scale, visibleRange)
  const ticks = useMemo(() => {
    const visMin = minTime + (minPct / 100) * range
    const visMax = minTime + (maxPct / 100) * range
    return generateTicks(Math.max(minTime, visMin), Math.min(maxTime, visMax))
  }, [minTime, maxTime, range, minPct, maxPct])

  // Edge indicators — show when there's off-screen content
  const showLeftFade = panX < -1
  const containerW = containerRef.current?.getBoundingClientRect().width ?? 0
  const showRightFade = scale > 1 && containerW > 0 && panX > containerW * (1 - scale) + 1

  if (range <= 0) {
    return <div className="text-[10px] text-muted-foreground">No time data</div>
  }

  const innerStyle = {
    width: `${scale * 100}%`,
    transform: `translateX(${panX}px)`,
  }

  // Compute pixel position of a handle for labels rendered above the pane
  const handleLeft = (pct: number) => `calc(${pct}% * ${scale} + ${panX}px)`

  return (
    <div className="relative pt-5">
      {/* Handle timestamp labels — above the pane, outside overflow */}
      {isDraggingWindow && (
        <>
          <span
            className="absolute top-0 -translate-x-1/2 text-[10px] font-medium text-primary-foreground bg-primary/80 rounded px-1 py-px whitespace-nowrap z-30 pointer-events-none"
            style={{ left: handleLeft(startPct) }}
          >
            {formatTimeOffset(effectiveStart, minTime)}
          </span>
          <span
            className="absolute top-0 -translate-x-1/2 text-[10px] font-medium text-primary-foreground bg-primary/80 rounded px-1 py-px whitespace-nowrap z-30 pointer-events-none"
            style={{ left: handleLeft(endPct) }}
          >
            {formatTimeOffset(effectiveEnd, minTime)}
          </span>
        </>
      )}

      <div
        ref={containerRef}
        className="relative w-full h-12 bg-muted rounded-lg cursor-grab overflow-hidden active:cursor-grabbing"
        onPointerDown={handleTrackPointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        onWheel={handleWheel}
      >
        {/* Inner track — scaled and translated for zoom */}
        <div className="absolute top-0 h-full" style={innerStyle}>
          {/* Tick dashed lines */}
          <TickLines ticks={ticks} toPercent={(t) => toPercent(t)} />

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
            className="absolute top-0 w-1 h-full bg-primary cursor-ew-resize hover:bg-primary/80"
            style={{ left: `${startPct}%`, marginLeft: -1 }}
            onPointerDown={(e) => handlePointerDown(e, 'start')}
          />

          {/* End handle */}
          <div
            className="absolute top-0 w-1 h-full bg-primary cursor-ew-resize hover:bg-primary/80"
            style={{ left: `${endPct}%`, marginLeft: -1 }}
            onPointerDown={(e) => handlePointerDown(e, 'end')}
          />
        </div>

        {/* Edge fade indicators */}
        <div
          className="absolute left-0 top-0 w-6 h-full bg-gradient-to-r from-foreground/15 to-transparent pointer-events-none z-10 transition-opacity duration-300"
          style={{ opacity: showLeftFade ? 1 : 0 }}
        />
        <div
          className="absolute right-0 top-0 w-6 h-full bg-gradient-to-l from-foreground/15 to-transparent pointer-events-none z-10 transition-opacity duration-300"
          style={{ opacity: showRightFade ? 1 : 0 }}
        />

        {/* Static edge marks */}
        <div className="absolute left-0 top-0 w-1 h-full bg-foreground/20 pointer-events-none z-10" />
        <div className="absolute right-0 top-0 w-1 h-full bg-foreground/20 pointer-events-none z-10" />
      </div>

      {/* Tick labels below the pane */}
      <div className="relative w-full h-5 overflow-hidden">
        <div className="absolute top-0 h-full" style={innerStyle}>
          {ticks.map((t, i) => (
            <span
              key={i}
              className="absolute top-0.5 text-[10px] text-muted-foreground -translate-x-1/2 leading-tight"
              style={{ left: `${toPercent(t)}%` }}
            >
              {formatTimeOffset(t, minTime)}
            </span>
          ))}
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
  const containerRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState<'handle' | 'pan' | null>(null)
  const dragStartX = useRef(0)
  const dragStartPanX = useRef(0)

  const [scale, setScale] = useState(1)
  const [panX, setPanX] = useState(0)

  const range = maxStep - minStep
  const pad = STEP_TRACK_PAD

  const toPercent = (s: number) => (range > 0 ? ((s - minStep) / range) * 100 : 50)

  // Map screen pixel → step value, accounting for zoom + padding
  const fromPixel = useCallback((px: number) => {
    if (!containerRef.current || range <= 0) return minStep
    const rect = containerRef.current.getBoundingClientRect()
    const innerLeft = rect.left + pad
    const innerWidth = rect.width - pad * 2
    const trackX = (px - innerLeft - panX) / scale
    const frac = Math.max(0, Math.min(1, trackX / innerWidth))
    return Math.round(minStep + frac * range)
  }, [minStep, range, scale, panX, pad])

  const clampPanX = useCallback((px: number, s: number) => {
    if (!containerRef.current || s <= 1) return 0
    const innerWidth = containerRef.current.getBoundingClientRect().width - pad * 2
    return Math.min(0, Math.max(innerWidth * (1 - s), px))
  }, [pad])

  // Handle drag (on the handle element)
  const handleHandlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    setDragging('handle')
    onChange(fromPixel(e.clientX))
  }, [fromPixel, onChange])

  // Pan drag (on empty space)
  const handleTrackPointerDown = useCallback((e: React.PointerEvent) => {
    if (dragging) return
    e.preventDefault()
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    setDragging('pan')
    dragStartX.current = e.clientX
    dragStartPanX.current = panX
  }, [dragging, panX])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return
    if (dragging === 'handle') {
      onChange(fromPixel(e.clientX))
    } else if (dragging === 'pan') {
      const dx = e.clientX - dragStartX.current
      setPanX(clampPanX(dragStartPanX.current + dx, scale))
    }
  }, [dragging, fromPixel, onChange, clampPanX, scale])

  const handlePointerUp = useCallback(() => {
    setDragging(null)
  }, [])

  const handleDoubleClick = useCallback(() => {
    onChange(null)
    setScale(1)
    setPanX(0)
  }, [onChange])

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    if (range <= 0 || !containerRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    const cursorX = e.clientX - rect.left - pad
    const innerWidth = rect.width - pad * 2

    const zoomFactor = e.deltaY < 0 ? 1.25 : 1 / 1.25
    const newScale = Math.max(1, Math.min(50, scale * zoomFactor))

    const trackPoint = (cursorX - panX) / scale
    let newPanX = cursorX - trackPoint * newScale

    newPanX = Math.min(0, Math.max(innerWidth * (1 - newScale), newPanX))

    if (newScale <= 1) {
      setScale(1)
      setPanX(0)
    } else {
      setScale(newScale)
      setPanX(newPanX)
    }
  }, [range, scale, panX, pad])

  const stepBy = useCallback((delta: number) => {
    if (range <= 0) return
    const current = value ?? minStep
    const next = Math.max(minStep, Math.min(maxStep, current + delta))
    onChange(next)
  }, [range, value, minStep, maxStep, onChange])

  // Ctrl+Left/Right arrow keys to step through (global)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (range <= 0) return
      if (!e.ctrlKey && !e.metaKey) return
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      e.preventDefault()
      stepBy(e.key === 'ArrowRight' ? 1 : -1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [range, stepBy])

  // Auto-pan to keep the handle visible when its value changes
  const prevValue = useRef(value)
  useEffect(() => {
    if (prevValue.current === value) return
    prevValue.current = value
    if (value == null || scale <= 1 || !containerRef.current) return
    const innerWidth = containerRef.current.getBoundingClientRect().width - pad * 2
    const frac = range > 0 ? (value - minStep) / range : 0
    setPanX(prev => {
      const handlePos = frac * innerWidth * scale + prev
      if (handlePos < 0) {
        return clampPanX(prev - handlePos, scale)
      } else if (handlePos > innerWidth) {
        return clampPanX(prev - (handlePos - innerWidth), scale)
      }
      return prev
    })
  }, [value, scale, range, minStep, pad, clampPanX])

  const stepEvents = useMemo(() => events.filter(ev => ev.step != null), [events])
  const stepContainerW = containerRef.current?.clientWidth ?? 300
  const stepInnerW = stepContainerW - pad * 2
  const stepMinPct = (-panX / (stepInnerW * scale)) * 100
  const stepMaxPct = stepMinPct + 100 / scale
  const stepVisibleRange = useMemo<[number, number]>(() => [stepMinPct - 2, stepMaxPct + 2], [stepMinPct, stepMaxPct])
  const dots = useEventDots(stepEvents, (ev) => toPercent(ev.step!), scale, stepVisibleRange)
  const ticks = useMemo(() => {
    const visMin = minStep + (stepMinPct / 100) * range
    const visMax = minStep + (stepMaxPct / 100) * range
    const raw = generateTicks(Math.max(minStep, visMin), Math.min(maxStep, visMax))
    return raw.map(t => Math.round(t))
  }, [minStep, maxStep, range, stepMinPct, stepMaxPct])

  if (!hasSteps) {
    return <div className="text-[10px] text-muted-foreground opacity-50">No step data</div>
  }

  const currentPct = value != null ? toPercent(value) : toPercent(minStep)

  const innerStyle = {
    width: `${scale * 100}%`,
    transform: `translateX(${panX}px)`,
  }

  // Edge fade indicators
  const showLeftFade = panX < -1
  const innerWidth = containerRef.current ? containerRef.current.getBoundingClientRect().width - pad * 2 : 0
  const showRightFade = scale > 1 && innerWidth > 0 && panX > innerWidth * (1 - scale) + 1

  const isMac = /Mac|iPhone|iPad/.test(navigator.userAgent)
  const modKey = isMac ? '\u2318' : 'Ctrl'

  return (
    <div className="relative pt-5">
      <div className="flex items-start gap-1">
        <button
          title={`Previous step (${modKey}+\u2190)`}
          className="shrink-0 h-12 flex items-center p-0.5 rounded hover:bg-muted-foreground/20 text-muted-foreground disabled:opacity-30"
          disabled={value != null && value <= minStep}
          onClick={() => stepBy(-1)}
        >
          <ChevronLeft size={16} />
        </button>

        <div className="flex-1 min-w-0">
          <div
            ref={containerRef}
            className="relative w-full h-12 bg-muted cursor-grab rounded-lg overflow-hidden active:cursor-grabbing"
            onPointerDown={handleTrackPointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onDoubleClick={handleDoubleClick}
            onWheel={handleWheel}
          >
            {/* Inset content area with zoom/pan */}
            <div className="absolute top-0 h-full" style={{ left: pad, right: pad }}>
              <div className="absolute top-0 h-full" style={innerStyle}>
                {/* Tick dashed lines */}
                <TickLines ticks={ticks} toPercent={(t) => toPercent(t)} />

                {/* Event dots */}
                <EventDotLayer dots={dots} inset={false} />

                {/* Handle */}
                <div
                  className={`absolute top-0 w-0.5 h-full cursor-ew-resize transition-[left] duration-150 ease-out ${
                    value != null ? 'bg-primary hover:bg-primary/80' : 'bg-muted-foreground/40'
                  }`}
                  style={{ left: `${currentPct}%`, transform: 'translateX(-50%)' }}
                  onPointerDown={handleHandlePointerDown}
                />
              </div>
            </div>

            {/* Edge fade indicators */}
            <div
              className="absolute left-0 top-0 w-6 h-full bg-gradient-to-r from-foreground/15 to-transparent pointer-events-none z-10 transition-opacity duration-300"
              style={{ opacity: showLeftFade ? 1 : 0 }}
            />
            <div
              className="absolute right-0 top-0 w-6 h-full bg-gradient-to-l from-foreground/15 to-transparent pointer-events-none z-10 transition-opacity duration-300"
              style={{ opacity: showRightFade ? 1 : 0 }}
            />

            {/* Static edge marks */}
            <div className="absolute left-0 top-0 w-1 h-full bg-foreground/20 pointer-events-none" />
            <div className="absolute right-0 top-0 w-1 h-full bg-foreground/20 pointer-events-none" />
          </div>

          {/* Tick labels below the pane */}
          <div className="relative w-full h-5 overflow-hidden">
            <div className="absolute top-0 h-full" style={{ left: pad, right: pad }}>
              <div className="absolute top-0 h-full" style={innerStyle}>
                {ticks.map((t, i) => (
                  <span
                    key={i}
                    className="absolute top-0.5 text-[10px] text-muted-foreground -translate-x-1/2 leading-tight"
                    style={{ left: `${toPercent(t)}%` }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <button
          title={`Next step (${modKey}+\u2192)`}
          className="shrink-0 h-12 flex items-center p-0.5 rounded hover:bg-muted-foreground/20 text-muted-foreground disabled:opacity-30"
          disabled={value != null && value >= maxStep}
          onClick={() => stepBy(1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

// --- Tick Lines (dashed vertical lines inside the pane) ---

function TickLines({ ticks, toPercent }: { ticks: number[]; toPercent: (t: number) => number }) {
  if (ticks.length === 0) return null
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none">
      {ticks.map((t, i) => {
        const pct = toPercent(t)
        return (
          <line
            key={i}
            x1={`${pct}%`}
            y1="0"
            x2={`${pct}%`}
            y2="100%"
            stroke="currentColor"
            className="text-foreground/15"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        )
      })}
    </svg>
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
  scale: number = 1,
  visibleRange?: [number, number],
): MergedDot[] {
  return useMemo(() => {
    if (events.length === 0) return []

    const bucketSize = 0.5 / scale
    const buckets = new Map<number, TimelineEvent[]>()

    for (const ev of events) {
      const pct = toPercent(ev)
      if (visibleRange && (pct < visibleRange[0] || pct > visibleRange[1])) continue
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
  }, [events, toPercent, scale, visibleRange])
}

function EventDotLayer({ dots, inset = true }: { dots: MergedDot[]; inset?: boolean }) {
  if (dots.length === 0) return null

  const style = inset
    ? { left: DOT_MARGIN, right: DOT_MARGIN, width: `calc(100% - ${DOT_MARGIN * 2}px)` }
    : undefined

  return (
    <svg
      className={`absolute top-0 h-full overflow-visible pointer-events-none ${inset ? '' : 'inset-0 w-full'}`}
      style={style}
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
