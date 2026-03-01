export type WsEventHandler = (event: WsBatchEvent) => void

export interface WsBatchEvent {
  type: 'batch'
  run_id: string
  events: WsEvent[]
}

export interface WsEvent {
  type: string
  node?: string
  data?: Record<string, unknown>
  message?: string
  name?: string
  value?: number
  step?: number
  level?: string
  timestamp?: number
  [key: string]: unknown
}

export class WebSocketManager {
  private ws: WebSocket | null = null
  private url: string
  private handlers: Set<WsEventHandler> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private _connected = false
  private _reconnecting = false

  constructor(url?: string) {
    const loc = window.location
    const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = url ?? `${wsProto}//${loc.host}/stream`
  }

  get connected() { return this._connected }
  get reconnecting() { return this._reconnecting }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this._connected = true
        this._reconnecting = false
        this.reconnectDelay = 1000
        this.notifyStatus()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WsBatchEvent
          this.handlers.forEach(h => h(data))
        } catch {
          // Ignore malformed messages
        }
      }

      this.ws.onclose = () => {
        this._connected = false
        this.scheduleReconnect()
      }

      this.ws.onerror = () => {
        this.ws?.close()
      }
    } catch {
      this.scheduleReconnect()
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this._reconnecting = false
    this.ws?.close()
    this.ws = null
    this._connected = false
  }

  subscribe(handler: WsEventHandler) {
    this.handlers.add(handler)
    return () => { this.handlers.delete(handler) }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this._reconnecting = true
    this.notifyStatus()
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      this.connect()
    }, this.reconnectDelay)
  }

  private notifyStatus() {
    // Status changes are handled by the store polling connected/reconnecting
  }
}
