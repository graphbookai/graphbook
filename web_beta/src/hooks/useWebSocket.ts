import { useEffect, useRef } from 'react'
import { WebSocketManager } from '@/lib/ws'
import { useStore } from '@/store'
import { api } from '@/lib/api'

export function useWebSocket() {
  const wsRef = useRef<WebSocketManager | null>(null)
  const processWsEvents = useStore(s => s.processWsEvents)
  const setConnectionStatus = useStore(s => s.setConnectionStatus)
  const setRuns = useStore(s => s.setRuns)

  useEffect(() => {
    const ws = new WebSocketManager()
    wsRef.current = ws

    // Subscribe to events
    const unsub = ws.subscribe((batch) => {
      if (batch.type === 'batch' && batch.run_id && batch.events) {
        processWsEvents(batch.run_id, batch.events)
      }
    })

    // Poll connection status
    const statusInterval = setInterval(() => {
      setConnectionStatus(ws.connected, ws.reconnecting)
    }, 500)

    // Initial data load
    api.listRuns()
      .then(data => setRuns(data.runs, data.active_run))
      .catch(() => { /* daemon not running */ })

    // Periodic refresh of run list
    const refreshInterval = setInterval(() => {
      api.listRuns()
        .then(data => setRuns(data.runs, data.active_run))
        .catch(() => { /* ignore */ })
    }, 5000)

    ws.connect()

    return () => {
      unsub()
      clearInterval(statusInterval)
      clearInterval(refreshInterval)
      ws.disconnect()
    }
  }, [processWsEvents, setConnectionStatus, setRuns])
}
