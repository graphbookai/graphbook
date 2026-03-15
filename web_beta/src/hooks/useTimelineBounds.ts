import { useMemo } from 'react'
import { useStore } from '@/store'

export interface TimelineEvent {
  timestamp: number
  step: number | null
  type: 'log' | 'image' | 'audio'
  node: string | null
  label: string
}

export interface TimelineBounds {
  minTime: number
  maxTime: number
  minStep: number
  maxStep: number
  hasSteps: boolean
  events: TimelineEvent[]
}

function formatLabel(type: string, offset: number, step: number | null, extra?: string): string {
  const t = offset < 60 ? `${offset.toFixed(1)}s` : `${(offset / 60).toFixed(1)}m`
  const parts = [type]
  parts.push(`· ${t}`)
  if (step != null) parts.push(`(step ${step})`)
  if (extra) parts.push(`· ${extra}`)
  return parts.join(' ')
}

export function useTimelineBounds(runId: string | null): TimelineBounds {
  const run = useStore(s => (runId ? s.runs.get(runId) : undefined))
  const logs = run?.logs
  const nodeImages = run?.nodeImages
  const nodeAudio = run?.nodeAudio

  return useMemo(() => {
    let minTime = Infinity
    let maxTime = -Infinity
    let minStep = Infinity
    let maxStep = -Infinity
    let hasSteps = false

    function trackTime(t: number) {
      if (t < minTime) minTime = t
      if (t > maxTime) maxTime = t
    }

    function trackStep(s: number | null | undefined) {
      if (s != null) {
        hasSteps = true
        if (s < minStep) minStep = s
        if (s > maxStep) maxStep = s
      }
    }

    const rawEvents: TimelineEvent[] = []

    if (logs) {
      for (const l of logs) {
        trackTime(l.timestamp)
        trackStep(l.step)
        rawEvents.push({
          timestamp: l.timestamp,
          step: l.step ?? null,
          type: 'log',
          node: l.node ?? null,
          label: '', // filled after minTime is known
        })
      }
    }

    if (nodeImages) {
      for (const [nodeName, imgs] of Object.entries(nodeImages)) {
        for (const img of imgs) {
          trackTime(img.timestamp)
          trackStep(img.step)
          rawEvents.push({
            timestamp: img.timestamp,
            step: img.step ?? null,
            type: 'image',
            node: nodeName,
            label: '',
          })
        }
      }
    }

    if (nodeAudio) {
      for (const [nodeName, entries] of Object.entries(nodeAudio)) {
        for (const a of entries) {
          trackTime(a.timestamp)
          trackStep(a.step)
          rawEvents.push({
            timestamp: a.timestamp,
            step: a.step ?? null,
            type: 'audio',
            node: nodeName,
            label: '',
          })
        }
      }
    }

    if (minTime === Infinity) minTime = 0
    if (maxTime === -Infinity) maxTime = 0
    if (minStep === Infinity) minStep = 0
    if (maxStep === -Infinity) maxStep = 0

    // Fill labels now that minTime is known
    for (const ev of rawEvents) {
      ev.label = formatLabel(ev.type, ev.timestamp - minTime, ev.step)
    }

    return { minTime, maxTime, minStep, maxStep, hasSteps, events: rawEvents }
  }, [logs, nodeImages, nodeAudio])
}
