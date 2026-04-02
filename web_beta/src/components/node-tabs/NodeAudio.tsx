import { useMemo } from 'react'
import { useStore, type AudioEntry } from '@/store'
import { useTimelineFilter } from '@/hooks/useTimelineFilter'
import { useMedia } from '@/hooks/useMedia'
import { formatTimestamp } from '@/lib/utils'
import { ComparisonGrid } from '@/components/shared/ComparisonGrid'

interface NodeAudioProps {
  runId: string
  nodeId: string
  comparisonRunIds?: string[]
}

export function NodeAudio({ runId, nodeId, comparisonRunIds }: NodeAudioProps) {
  if (comparisonRunIds) {
    return (
      <ComparisonGrid runIds={comparisonRunIds}>
        {(cellRunId) => <ComparisonAudioCell runId={cellRunId} nodeId={nodeId} />}
      </ComparisonGrid>
    )
  }

  return <SingleRunAudio runId={runId} nodeId={nodeId} />
}

function AudioItem({ runId, entry, showTimestamp }: { runId: string; entry: AudioEntry; showTimestamp?: boolean }) {
  const { data, loading } = useMedia(runId, entry.mediaId)

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className={`${showTimestamp ? 'text-xs' : 'text-[10px]'} font-medium`}>{entry.name}</span>
        <span className="text-[10px] text-muted-foreground">
          {entry.sr}Hz
          {showTimestamp && ` · ${formatTimestamp(entry.timestamp)}`}
        </span>
      </div>
      {loading ? (
        <div className="rounded border border-border bg-muted/50 animate-pulse h-8 w-full" />
      ) : data ? (
        <audio
          controls
          src={`data:audio/wav;base64,${data}`}
          className="w-full h-8"
        />
      ) : (
        <div className="rounded border border-border bg-muted/30 h-8 w-full flex items-center justify-center">
          <span className="text-[10px] text-muted-foreground">Failed to load</span>
        </div>
      )}
    </div>
  )
}

function ComparisonAudioCell({ runId, nodeId }: { runId: string; nodeId: string }) {
  const allAudioEntries = useStore(s => s.runs.get(runId)?.nodeAudio[nodeId]) ?? []
  const timelineFilter = useTimelineFilter()

  const audioEntries = useMemo(() => {
    if (!timelineFilter) return allAudioEntries
    return allAudioEntries.filter(entry => timelineFilter.matchEntry(entry))
  }, [allAudioEntries, timelineFilter])

  if (audioEntries.length === 0) {
    return <p className="text-xs text-muted-foreground p-2">No audio</p>
  }

  return (
    <div className="space-y-2 p-1">
      {audioEntries.map((entry) => (
        <AudioItem key={entry.mediaId} runId={runId} entry={entry} />
      ))}
    </div>
  )
}

function SingleRunAudio({ runId, nodeId }: { runId: string; nodeId: string }) {
  const allAudioEntries = useStore(s => s.runs.get(runId)?.nodeAudio[nodeId]) ?? []
  const timelineFilter = useTimelineFilter()

  const audioEntries = useMemo(() => {
    if (!timelineFilter) return allAudioEntries
    return allAudioEntries.filter(entry => timelineFilter.matchEntry(entry))
  }, [allAudioEntries, timelineFilter])

  if (audioEntries.length === 0) {
    return <p className="text-xs text-muted-foreground">No audio for this node</p>
  }

  return (
    <div className="space-y-3">
      {audioEntries.map((entry) => (
        <AudioItem key={entry.mediaId} runId={runId} entry={entry} showTimestamp />
      ))}
    </div>
  )
}
