import { useStore } from '@/store'
import { formatTimestamp } from '@/lib/utils'

interface NodeAudioProps {
  runId: string
  nodeId: string
}

export function NodeAudio({ runId, nodeId }: NodeAudioProps) {
  const audioEntries = useStore(s => s.runs.get(runId)?.nodeAudio[nodeId]) ?? []

  if (audioEntries.length === 0) {
    return <p className="text-xs text-muted-foreground">No audio for this node</p>
  }

  return (
    <div className="space-y-3">
      {audioEntries.map((entry, i) => (
        <div key={i} className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">{entry.name}</span>
            <span className="text-[10px] text-muted-foreground">
              {entry.sr}Hz · {formatTimestamp(entry.timestamp)}
            </span>
          </div>
          <audio
            controls
            src={`data:audio/wav;base64,${entry.data}`}
            className="w-full h-8"
          />
        </div>
      ))}
    </div>
  )
}
