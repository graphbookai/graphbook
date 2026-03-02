import { useMemo } from 'react'
import { useStore } from '@/store'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface NodeMetricsProps {
  runId: string
  nodeId: string
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

export function NodeMetrics({ runId, nodeId }: NodeMetricsProps) {
  const metrics = useStore(s => s.runs.get(runId)?.nodeMetrics[nodeId])

  const metricEntries = useMemo(() => {
    if (!metrics) return []
    return Object.entries(metrics).map(([name, series]) => ({
      name,
      data: downsample(series),
    }))
  }, [metrics])

  if (metricEntries.length === 0) {
    return <p className="text-xs text-muted-foreground">No metrics for this node</p>
  }

  return (
    <div className="space-y-4">
      {metricEntries.map(({ name, data }) => (
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
