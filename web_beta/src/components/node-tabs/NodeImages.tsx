import { useStore } from '@/store'
import { formatTimestamp } from '@/lib/utils'

interface NodeImagesProps {
  runId: string
  nodeId: string
}

export function NodeImages({ runId, nodeId }: NodeImagesProps) {
  const images = useStore(s => s.runs.get(runId)?.nodeImages[nodeId]) ?? []

  if (images.length === 0) {
    return <p className="text-xs text-muted-foreground">No images for this node</p>
  }

  return (
    <div className="space-y-3">
      {images.map((img, i) => (
        <div key={i} className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">{img.name}</span>
            <span className="text-[10px] text-muted-foreground">
              {img.step != null && `step ${img.step} · `}
              {formatTimestamp(img.timestamp)}
            </span>
          </div>
          <img
            src={`data:image/png;base64,${img.data}`}
            alt={img.name}
            className="rounded border border-border max-w-full"
          />
        </div>
      ))}
    </div>
  )
}
