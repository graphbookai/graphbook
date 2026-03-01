import { cn } from '@/lib/utils'

interface RunStatusBadgeProps {
  status: string
  className?: string
}

const statusConfig: Record<string, { icon: string; color: string; label: string; animate?: string }> = {
  starting: { icon: '◌', color: 'text-yellow-500', label: 'Starting' },
  running: { icon: '●', color: 'text-blue-500', label: 'Running', animate: 'animate-pulse-running' },
  completed: { icon: '✓', color: 'text-green-500', label: 'Completed' },
  crashed: { icon: '✗', color: 'text-red-500', label: 'Crashed' },
  stopped: { icon: '■', color: 'text-yellow-500', label: 'Stopped' },
}

export function RunStatusBadge({ status, className }: RunStatusBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.stopped

  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', className)}>
      <span className={cn(config.color, config.animate)}>{config.icon}</span>
      <span className={cn(config.color)}>{config.label}</span>
    </span>
  )
}
