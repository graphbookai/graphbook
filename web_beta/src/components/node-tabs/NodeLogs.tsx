import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useStore } from '@/store'
import { useTimelineFilter } from '@/hooks/useTimelineFilter'
import { formatTimestamp } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { Search } from 'lucide-react'
import { ComparisonGrid } from '@/components/shared/ComparisonGrid'

interface NodeLogsProps {
  runId: string
  nodeId: string
  comparisonRunIds?: string[]
}

const levels = ['All', 'Info', 'Warn', 'Error'] as const

export function NodeLogs({ runId, nodeId, comparisonRunIds }: NodeLogsProps) {
  const [search, setSearch] = useState('')
  const [levelFilter, setLevelFilter] = useState<string>('All')

  if (comparisonRunIds) {
    return (
      <div className="space-y-2">
        {/* Shared search and filter */}
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

        <ComparisonGrid runIds={comparisonRunIds}>
          {(cellRunId) => (
            <ComparisonLogCell
              runId={cellRunId}
              nodeId={nodeId}
              search={search}
              levelFilter={levelFilter}
            />
          )}
        </ComparisonGrid>
      </div>
    )
  }

  return (
    <SingleRunLogs
      runId={runId}
      nodeId={nodeId}
      search={search}
      setSearch={setSearch}
      levelFilter={levelFilter}
      setLevelFilter={setLevelFilter}
    />
  )
}

interface ComparisonLogCellProps {
  runId: string
  nodeId: string
  search: string
  levelFilter: string
}

function ComparisonLogCell({ runId, nodeId, search, levelFilter }: ComparisonLogCellProps) {
  const logs = useStore(s => s.runs.get(runId)?.logs ?? [])
  const errors = useStore(s => s.runs.get(runId)?.errors ?? [])
  const timelineFilter = useTimelineFilter()

  const nodeErrors = useMemo(() => errors.filter(e => e.node_name === nodeId), [errors, nodeId])

  const nodeLogs = useMemo(() => {
    let filtered = logs.filter(l => l.node === nodeId)
    if (levelFilter !== 'All') {
      const lvl = levelFilter.toLowerCase()
      filtered = filtered.filter(l => l.level === lvl)
    }
    if (search) {
      const q = search.toLowerCase()
      filtered = filtered.filter(l => l.message.toLowerCase().includes(q))
    }
    if (timelineFilter) {
      filtered = filtered.filter(l => timelineFilter.matchEntry(l))
    }
    return filtered
  }, [logs, nodeId, levelFilter, search, timelineFilter])

  if (nodeLogs.length === 0 && nodeErrors.length === 0) {
    return <p className="text-xs text-muted-foreground p-2">No logs</p>
  }

  return (
    <div className="max-h-[200px] overflow-auto p-1">
      {nodeLogs.map((log, i) => (
        <div
          key={i}
          className={cn(
            'text-xs font-mono py-0.5 px-1 rounded',
            log.level === 'error' && 'bg-red-500/10 text-red-400',
            log.level === 'warning' && 'text-yellow-400',
          )}
        >
          <span className="text-muted-foreground mr-2">{formatTimestamp(log.timestamp)}</span>
          <span>{log.message}</span>
        </div>
      ))}
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
  )
}

interface SingleRunLogsProps {
  runId: string
  nodeId: string
  search: string
  setSearch: (v: string) => void
  levelFilter: string
  setLevelFilter: (v: string) => void
}

function SingleRunLogs({ runId, nodeId, search, setSearch, levelFilter, setLevelFilter }: SingleRunLogsProps) {
  const logs = useStore(s => s.runs.get(runId)?.logs ?? [])
  const errors = useStore(s => s.runs.get(runId)?.errors ?? [])
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const timelineFilter = useTimelineFilter()

  const nodeErrors = useMemo(() => errors.filter(e => e.node_name === nodeId), [errors, nodeId])

  const nodeLogs = useMemo(() => {
    let filtered = logs.filter(l => l.node === nodeId)
    if (levelFilter !== 'All') {
      const lvl = levelFilter.toLowerCase()
      filtered = filtered.filter(l => l.level === lvl)
    }
    if (search) {
      const q = search.toLowerCase()
      filtered = filtered.filter(l => l.message.toLowerCase().includes(q))
    }
    if (timelineFilter) {
      filtered = filtered.filter(l => timelineFilter.matchEntry(l))
    }
    return filtered
  }, [logs, nodeId, levelFilter, search, timelineFilter])

  const allNodeLogs = useMemo(() => logs.filter(l => l.node === nodeId), [logs, nodeId])

  if (allNodeLogs.length === 0 && nodeErrors.length === 0) {
    return <p className="text-xs text-muted-foreground">No logs for this node</p>
  }

  return (
    <NodeLogsInner
      nodeLogs={nodeLogs}
      nodeErrors={nodeErrors}
      search={search}
      setSearch={setSearch}
      levelFilter={levelFilter}
      setLevelFilter={setLevelFilter}
      scrollRef={scrollRef}
      autoScroll={autoScroll}
      setAutoScroll={setAutoScroll}
    />
  )
}

interface NodeLogsInnerProps {
  nodeLogs: { timestamp: number; node: string | null; message: string; level: string }[]
  nodeErrors: { exception_type: string; exception_message: string; traceback: string }[]
  search: string
  setSearch: (v: string) => void
  levelFilter: string
  setLevelFilter: (v: string) => void
  scrollRef: React.RefObject<HTMLDivElement | null>
  autoScroll: boolean
  setAutoScroll: (v: boolean) => void
}

function NodeLogsInner({
  nodeLogs,
  nodeErrors,
  search,
  setSearch,
  levelFilter,
  setLevelFilter,
  scrollRef,
  autoScroll,
  setAutoScroll,
}: NodeLogsInnerProps) {
  const virtualizer = useVirtualizer({
    count: nodeLogs.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 20,
    overscan: 20,
  })

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && nodeLogs.length > 0) {
      virtualizer.scrollToIndex(nodeLogs.length - 1, { align: 'end' })
    }
  }, [nodeLogs.length, autoScroll, virtualizer])

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 30)
  }, [scrollRef, setAutoScroll])

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

      {/* Virtualized log entries */}
      <div ref={scrollRef} className="max-h-[200px] overflow-auto" onScroll={handleScroll}>
        <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
          {virtualizer.getVirtualItems().map(virtualItem => {
            const log = nodeLogs[virtualItem.index]
            return (
              <div
                key={virtualItem.index}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualItem.start}px)`,
                }}
                className={cn(
                  'text-xs font-mono py-0.5 px-1 rounded',
                  log.level === 'error' && 'bg-red-500/10 text-red-400',
                  log.level === 'warning' && 'text-yellow-400',
                )}
              >
                <span className="text-muted-foreground mr-2">{formatTimestamp(log.timestamp)}</span>
                <span>{log.message}</span>
              </div>
            )
          })}
        </div>

        {/* Error tracebacks (outside virtualizer — typically few, variable height) */}
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
            if (nodeLogs.length > 0) {
              virtualizer.scrollToIndex(nodeLogs.length - 1, { align: 'end' })
            }
          }}
        >
          Jump to latest
        </button>
      )}
    </div>
  )
}
