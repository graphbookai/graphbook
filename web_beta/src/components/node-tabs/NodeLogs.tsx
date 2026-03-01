import { useState, useRef, useEffect } from 'react'
import { useStore } from '@/store'
import { formatTimestamp } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { Search } from 'lucide-react'

interface NodeLogsProps {
  runId: string
  nodeId: string
}

const levels = ['All', 'Info', 'Warn', 'Error'] as const

export function NodeLogs({ runId, nodeId }: NodeLogsProps) {
  const run = useStore(s => s.runs.get(runId))
  const [search, setSearch] = useState('')
  const [levelFilter, setLevelFilter] = useState<string>('All')
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Filter logs for this node
  const allLogs = run?.logs ?? []
  let nodeLogs = allLogs.filter(l => l.node === nodeId)

  // Also include error entries as log-like entries
  const nodeErrors = (run?.errors ?? []).filter(e => e.node_name === nodeId)

  if (levelFilter !== 'All') {
    const lvl = levelFilter.toLowerCase()
    nodeLogs = nodeLogs.filter(l => l.level === lvl)
  }

  if (search) {
    const q = search.toLowerCase()
    nodeLogs = nodeLogs.filter(l => l.message.toLowerCase().includes(q))
  }

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [nodeLogs.length, autoScroll])

  const handleScroll = () => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 30)
  }

  if (nodeLogs.length === 0 && nodeErrors.length === 0) {
    return <p className="text-xs text-muted-foreground">No logs for this node</p>
  }

  return (
    <div className="space-y-2">
      {/* Search and filter */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1 flex-1 bg-muted rounded-md px-2">
          <Search className="h-3 w-3 text-muted-foreground shrink-0" />
          <input
            type="text"
            placeholder="Search logs..."
            className="bg-transparent border-none outline-none text-xs py-1 w-full"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-0.5">
          {levels.map(lvl => (
            <button
              key={lvl}
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-medium transition-colors',
                levelFilter === lvl ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
              )}
              onClick={() => setLevelFilter(lvl)}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      {/* Log entries */}
      <div ref={scrollRef} className="max-h-[200px] overflow-auto space-y-0.5" onScroll={handleScroll}>
        {nodeLogs.map((log, i) => (
          <div key={i} className={cn(
            'text-xs font-mono py-0.5 px-1 rounded',
            log.level === 'error' && 'bg-red-500/10 text-red-400',
            log.level === 'warning' && 'text-yellow-400',
          )}>
            <span className="text-muted-foreground mr-2">{formatTimestamp(log.timestamp)}</span>
            <span>{log.message}</span>
          </div>
        ))}

        {/* Error tracebacks */}
        {nodeErrors.map((err, i) => (
          <div key={`err-${i}`} className="text-xs bg-red-500/10 rounded p-2 mt-1">
            <div className="font-medium text-red-400">
              {err.exception_type}: {err.exception_message}
            </div>
            {err.traceback && (
              <pre className="mt-1 text-[10px] text-red-300/70 overflow-auto whitespace-pre-wrap">
                {err.traceback}
              </pre>
            )}
          </div>
        ))}
      </div>

      {/* Jump to latest */}
      {!autoScroll && (
        <button
          className="text-[10px] text-blue-400 hover:underline"
          onClick={() => {
            setAutoScroll(true)
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
          }}
        >
          Jump to latest
        </button>
      )}
    </div>
  )
}
