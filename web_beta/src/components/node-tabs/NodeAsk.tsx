import { useState } from 'react'
import { useStore } from '@/store'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Send, Clock } from 'lucide-react'

interface NodeAskProps {
  runId: string
  nodeId: string
}

export function NodeAsk({ runId, nodeId }: NodeAskProps) {
  const run = useStore(s => s.runs.get(runId))
  const removeAskPrompt = useStore(s => s.removeAskPrompt)
  const [customResponse, setCustomResponse] = useState('')
  const [responding, setResponding] = useState(false)

  // Find pending asks for this node
  const pendingAsks = Array.from(run?.pendingAsks?.values() ?? [])
    .filter(a => a.nodeName === nodeId)

  if (pendingAsks.length === 0) {
    return <p className="text-xs text-muted-foreground">No pending questions</p>
  }

  const handleRespond = async (askId: string, response: string) => {
    setResponding(true)
    try {
      await api.respondToAsk(runId, askId, response)
      removeAskPrompt(runId, askId)
    } catch (err) {
      console.error('Failed to respond to ask:', err)
    } finally {
      setResponding(false)
      setCustomResponse('')
    }
  }

  return (
    <div className="space-y-4">
      {pendingAsks.map(ask => {
        const elapsed = ask.timeoutSeconds
          ? Math.max(0, ask.timeoutSeconds - Math.floor((Date.now() - ask.receivedAt.getTime()) / 1000))
          : null

        return (
          <div key={ask.askId} className="space-y-3">
            {/* Question */}
            <p className="text-sm text-foreground">{ask.question}</p>

            {/* Option buttons */}
            {ask.options && ask.options.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {ask.options.map(opt => (
                  <Button
                    key={opt}
                    variant="outline"
                    size="sm"
                    disabled={responding}
                    onClick={() => handleRespond(ask.askId, opt)}
                  >
                    {opt}
                  </Button>
                ))}
              </div>
            )}

            {/* Custom response */}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Or type a custom response..."
                className="flex-1 bg-muted rounded-md px-3 py-1.5 text-xs border border-input outline-none focus:ring-1 focus:ring-ring"
                value={customResponse}
                onChange={e => setCustomResponse(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && customResponse.trim()) {
                    handleRespond(ask.askId, customResponse.trim())
                  }
                }}
                disabled={responding}
                autoFocus
              />
              <Button
                size="sm"
                disabled={responding || !customResponse.trim()}
                onClick={() => handleRespond(ask.askId, customResponse.trim())}
              >
                <Send className="h-3 w-3" />
              </Button>
            </div>

            {/* Timeout */}
            {elapsed !== null && (
              <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>Timeout in {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}</span>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
