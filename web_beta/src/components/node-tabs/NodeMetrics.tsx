import { useMemo } from 'react'
import { useStore } from '@/store'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface NodeMetricsProps {
  runId: string
  nodeId: string
  comparisonRunIds?: string[]
}

const MAX_DISPLAY_POINTS = 500

function downsample(series: { step: number; value: number }[]): { step: number; value: number }[] {
  if (series.length <= MAX_DISPLAY_POINTS) return series
  const step = Math.ceil(series.length / MAX_DISPLAY_POINTS)
  const result: { step: number; value: number }[] = []
  for (let i = 0; i < series.length; i += step) {
    result.push(series[i])
  }
  // Always include the last point
  if (result[result.length - 1] !== series[series.length - 1]) {
    result.push(series[series.length - 1])
  }
  return result
}

export function NodeMetrics({ runId, nodeId, comparisonRunIds }: NodeMetricsProps) {
  const runs = useStore(s => s.runs)
  const runColors = useStore(s => s.runColors)
  const runNames = useStore(s => s.runNames)
  const metrics = useStore(s => s.runs.get(runId)?.nodeMetrics[nodeId])

  // Single-run mode
  const singleMetricEntries = useMemo(() => {
    if (comparisonRunIds) return []
    if (!metrics) return []
    return Object.entries(metrics).map(([name, series]) => ({
      name,
      data: downsample(series),
    }))
  }, [metrics, comparisonRunIds])

  // Comparison mode: merge metrics from all runs
  const comparisonMetricEntries = useMemo(() => {
    if (!comparisonRunIds) return []

    // Collect all metric names across all runs
    const metricNames = new Set<string>()
    for (const rid of comparisonRunIds) {
      const runMetrics = runs.get(rid)?.nodeMetrics[nodeId]
      if (runMetrics) {
        for (const name of Object.keys(runMetrics)) {
          metricNames.add(name)
        }
      }
    }

    return Array.from(metricNames).map(metricName => {
      // Merge data: collect all steps, then for each step build a row with per-run values
      const stepMap = new Map<number, Record<string, number>>()

      for (const rid of comparisonRunIds) {
        const series = runs.get(rid)?.nodeMetrics[nodeId]?.[metricName]
        if (!series) continue
        const downsampled = downsample(series)
        for (const point of downsampled) {
          if (!stepMap.has(point.step)) {
            stepMap.set(point.step, { step: point.step })
          }
          stepMap.get(point.step)![rid] = point.value
        }
      }

      const data = Array.from(stepMap.values()).sort((a, b) => a.step - b.step)
      return { name: metricName, data }
    })
  }, [comparisonRunIds, runs, nodeId])

  if (comparisonRunIds) {
    if (comparisonMetricEntries.length === 0) {
      return <p className="text-xs text-muted-foreground">No metrics for this node</p>
    }

    return (
      <div className="space-y-4">
        {comparisonMetricEntries.map(({ name, data }) => (
          <div key={name}>
            <span className="text-xs font-medium text-foreground">{name}</span>
            <div className="h-[120px] mt-1">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.3 0 0)" />
                  <XAxis
                    dataKey="step"
                    tick={{ fontSize: 10, fill: 'oklch(0.556 0 0)' }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: 'oklch(0.556 0 0)' }}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'oklch(0.205 0 0)',
                      border: '1px solid oklch(0.3 0 0)',
                      borderRadius: '6px',
                      fontSize: '11px',
                    }}
                    labelStyle={{ color: 'oklch(0.708 0 0)' }}
                    formatter={(value, dataKey) => {
                      const key = String(dataKey ?? '')
                      const displayName = runNames.get(key) || runs.get(key)?.summary.script_path.split('/').pop() || key
                      return [value != null ? Number(value).toFixed(4) : '', displayName]
                    }}
                    labelFormatter={(step) => `Step ${step}`}
                  />
                  {comparisonRunIds.map(rid => (
                    <Line
                      key={rid}
                      type="monotone"
                      dataKey={rid}
                      stroke={runColors.get(rid) ?? '#60a5fa'}
                      strokeWidth={1.5}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-3 mt-1">
              {comparisonRunIds.map(rid => {
                const color = runColors.get(rid) ?? '#60a5fa'
                const displayName = runNames.get(rid) || runs.get(rid)?.summary.script_path.split('/').pop() || rid
                return (
                  <div key={rid} className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-[10px] text-muted-foreground">{displayName}</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Single-run mode
  if (singleMetricEntries.length === 0) {
    return <p className="text-xs text-muted-foreground">No metrics for this node</p>
  }

  return (
    <div className="space-y-4">
      {singleMetricEntries.map(({ name, data }) => (
        <div key={name}>
          <span className="text-xs font-medium text-foreground">{name}</span>
          <div className="h-[120px] mt-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.3 0 0)" />
                <XAxis
                  dataKey="step"
                  tick={{ fontSize: 10, fill: 'oklch(0.556 0 0)' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: 'oklch(0.556 0 0)' }}
                  tickLine={false}
                  axisLine={false}
                  width={40}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'oklch(0.205 0 0)',
                    border: '1px solid oklch(0.3 0 0)',
                    borderRadius: '6px',
                    fontSize: '11px',
                  }}
                  labelStyle={{ color: 'oklch(0.708 0 0)' }}
                  formatter={(value) => [(value as number)?.toFixed(4) ?? '', name]}
                  labelFormatter={(step) => `Step ${step}`}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#3b82f6"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
    </div>
  )
}
