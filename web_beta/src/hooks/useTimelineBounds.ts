import { useMemo } from 'react'
import { useStore } from '@/store'

export interface TimelineBounds {
  minTime: number
  maxTime: number
  minStep: number
  maxStep: number
  hasSteps: boolean
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

    if (logs) {
      for (const l of logs) {
        trackTime(l.timestamp)
        trackStep(l.step)
      }
    }

    if (nodeImages) {
      for (const imgs of Object.values(nodeImages)) {
        for (const img of imgs) {
          trackTime(img.timestamp)
          trackStep(img.step)
        }
      }
    }

    if (nodeAudio) {
      for (const entries of Object.values(nodeAudio)) {
        for (const a of entries) {
          trackTime(a.timestamp)
          trackStep(a.step)
        }
      }
    }

    if (minTime === Infinity) minTime = 0
    if (maxTime === -Infinity) maxTime = 0
    if (minStep === Infinity) minStep = 0
    if (maxStep === -Infinity) maxStep = 0

    return { minTime, maxTime, minStep, maxStep, hasSteps }
  }, [logs, nodeImages, nodeAudio])
}
