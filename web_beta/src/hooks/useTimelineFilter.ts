import { useMemo } from 'react'
import { useStore } from '@/store'

interface Filterable {
  timestamp: number
  step?: number | null
}

export interface TimelineFilter {
  matchEntry: (entry: Filterable) => boolean
}

export function useTimelineFilter(): TimelineFilter | null {
  const timeline = useStore(s => s.timeline)

  return useMemo(() => {
    if (timeline.mode === 'time') {
      if (timeline.timeStart == null && timeline.timeEnd == null) return null
      return {
        matchEntry: (entry: Filterable) => {
          if (timeline.timeStart != null && entry.timestamp < timeline.timeStart) return false
          if (timeline.timeEnd != null && entry.timestamp > timeline.timeEnd) return false
          return true
        },
      }
    }

    // step mode
    if (timeline.step == null) return null
    return {
      matchEntry: (entry: Filterable) => entry.step === timeline.step,
    }
  }, [timeline.mode, timeline.timeStart, timeline.timeEnd, timeline.step])
}
