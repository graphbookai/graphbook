import { useMemo } from 'react'
import { useStore } from '@/store'
import { ComparisonGrid } from '@/components/shared/ComparisonGrid'

interface NodeInfoProps {
  runId: string
  nodeId: string
  comparisonRunIds?: string[]
}

export function NodeInfo({ runId, nodeId, comparisonRunIds }: NodeInfoProps) {
  const runs = useStore(s => s.runs)

  // Compute which params differ between runs (for highlighting)
  const differingParams = useMemo(() => {
    if (!comparisonRunIds || comparisonRunIds.length < 2) return new Set<string>()
    const diffSet = new Set<string>()
    const firstRun = runs.get(comparisonRunIds[0])
    const firstParams = firstRun?.graph?.nodes[nodeId]?.params
    if (!firstParams) return diffSet

    for (let i = 1; i < comparisonRunIds.length; i++) {
      const otherParams = runs.get(comparisonRunIds[i])?.graph?.nodes[nodeId]?.params
      if (!otherParams) {
        // If one run doesn't have this node, all params differ
        for (const k of Object.keys(firstParams)) diffSet.add(k)
        continue
      }
      // Check keys in first
      for (const k of Object.keys(firstParams)) {
        if (JSON.stringify(firstParams[k]) !== JSON.stringify(otherParams[k])) {
          diffSet.add(k)
        }
      }
      // Check keys only in other
      for (const k of Object.keys(otherParams)) {
        if (!(k in firstParams)) diffSet.add(k)
      }
    }
    return diffSet
  }, [comparisonRunIds, runs, nodeId])

  if (comparisonRunIds) {
    return (
      <ComparisonGrid runIds={comparisonRunIds}>
        {(cellRunId) => (
          <ComparisonInfoCell
            runId={cellRunId}
            nodeId={nodeId}
            differingParams={differingParams}
          />
        )}
      </ComparisonGrid>
    )
  }

  return <SingleRunInfo runId={runId} nodeId={nodeId} />
}

interface ComparisonInfoCellProps {
  runId: string
  nodeId: string
  differingParams: Set<string>
}

function ComparisonInfoCell({ runId, nodeId, differingParams }: ComparisonInfoCellProps) {
  const run = useStore(s => s.runs.get(runId))
  const nodeInfo = run?.graph?.nodes[nodeId]

  if (!nodeInfo) return <p className="text-xs text-muted-foreground p-2">Node not found</p>

  return (
    <div className="space-y-2 text-xs p-2">
      <div>
        <div className="flex items-center justify-between">
          <span className="font-medium">{nodeInfo.func_name}</span>
          <span className="text-muted-foreground">x{nodeInfo.exec_count}</span>
        </div>
        {nodeInfo.is_source && (
          <span className="inline-block mt-0.5 text-purple-500 text-[10px] font-medium">Source node</span>
        )}
      </div>

      {Object.keys(nodeInfo.params).length > 0 && (
        <div>
          <span className="text-muted-foreground font-medium">Config</span>
          <div className="mt-1 space-y-0.5">
            {Object.entries(nodeInfo.params).map(([k, v]) => (
              <div
                key={k}
                className={`flex justify-between gap-2 ${differingParams.has(k) ? 'bg-yellow-500/10 rounded px-1 -mx-1' : ''}`}
              >
                <span className="text-muted-foreground">{k}</span>
                <span className="text-foreground font-mono">{JSON.stringify(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {nodeInfo.progress && (
        <div>
          <span className="text-muted-foreground font-medium">Progress</span>
          <div className="mt-1">
            <div className="flex justify-between text-[10px] text-muted-foreground mb-0.5">
              <span>{nodeInfo.progress.name ?? ''}</span>
              <span>{nodeInfo.progress.current}/{nodeInfo.progress.total}</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{ width: `${(nodeInfo.progress.current / nodeInfo.progress.total) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SingleRunInfo({ runId, nodeId }: { runId: string; nodeId: string }) {
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
