import { useStore } from '@/store'

interface NodeInfoProps {
  runId: string
  nodeId: string
}

export function NodeInfo({ runId, nodeId }: NodeInfoProps) {
  const run = useStore(s => s.runs.get(runId))
  const nodeInfo = run?.graph?.nodes[nodeId]
  const inspections = run?.inspections[nodeId]

  if (!nodeInfo) return <p className="text-xs text-muted-foreground">Node not found</p>

  return (
    <div className="space-y-3 text-xs">
      {/* Name and count */}
      <div>
        <div className="flex items-center justify-between">
          <span className="font-medium text-sm">{nodeInfo.func_name}</span>
          <span className="text-muted-foreground">x{nodeInfo.exec_count}</span>
        </div>
        {nodeInfo.is_source && (
          <span className="inline-block mt-0.5 text-purple-500 text-[10px] font-medium">Source node</span>
        )}
      </div>

      {/* Docstring */}
      {nodeInfo.docstring && (
        <div>
          <span className="text-muted-foreground font-medium">Docstring</span>
          <p className="mt-0.5 text-foreground whitespace-pre-wrap">{nodeInfo.docstring}</p>
        </div>
      )}

      {/* Config params */}
      {Object.keys(nodeInfo.params).length > 0 && (
        <div>
          <span className="text-muted-foreground font-medium">Config</span>
          <div className="mt-1 space-y-0.5">
            {Object.entries(nodeInfo.params).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <span className="text-muted-foreground">{k}</span>
                <span className="text-foreground font-mono">{JSON.stringify(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress */}
      {nodeInfo.progress && (
        <div>
          <span className="text-muted-foreground font-medium">Progress</span>
          <div className="mt-1">
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>{nodeInfo.progress.name ?? ''}</span>
              <span>{nodeInfo.progress.current}/{nodeInfo.progress.total}</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${(nodeInfo.progress.current / nodeInfo.progress.total) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Inspections */}
      {inspections && Object.keys(inspections).length > 0 && (
        <div>
          <span className="text-muted-foreground font-medium">Inspections</span>
          <div className="mt-1 space-y-1">
            {Object.entries(inspections).map(([name, data]) => (
              <div key={name} className="bg-muted rounded p-2">
                <span className="font-medium">{name}</span>
                <pre className="mt-0.5 text-[10px] text-muted-foreground overflow-auto">
                  {JSON.stringify(data, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
