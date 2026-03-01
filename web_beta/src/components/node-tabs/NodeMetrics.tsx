import { useStore } from '@/store'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface NodeMetricsProps {
  runId: string
  nodeId: string
}

export function NodeMetrics({ runId, nodeId }: NodeMetricsProps) {
  const run = useStore(s => s.runs.get(runId))
  const metrics = run?.nodeMetrics[nodeId]

  if (!metrics || Object.keys(metrics).length === 0) {
    return <p className="text-xs text-muted-foreground">No metrics for this node</p>
  }

  return (
    <div className="space-y-4">
      {Object.entries(metrics).map(([name, series]) => (
        <div key={name}>
          <span className="text-xs font-medium text-foreground">{name}</span>
          <div className="h-[120px] mt-1">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series}>
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
                  animationDuration={300}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
    </div>
  )
}
