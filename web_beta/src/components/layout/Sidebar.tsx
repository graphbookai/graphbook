import { useStore } from '@/store'
import { RunList } from '@/components/runs/RunList'
import { SettingsPanel } from './SettingsPanel'
import { Wifi, WifiOff } from 'lucide-react'

export function Sidebar() {
  const connected = useStore(s => s.connected)

  return (
    <div className="flex flex-col h-full bg-sidebar border-r border-sidebar-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-sidebar-border">
        <h1 className="text-lg font-semibold text-sidebar-foreground">Graphbook</h1>
        <div className="flex items-center gap-1">
          {connected ? (
            <Wifi className="h-4 w-4 text-green-500" />
          ) : (
            <WifiOff className="h-4 w-4 text-muted-foreground" />
          )}
          <SettingsPanel />
        </div>
      </div>

      {/* Run list */}
      <div className="flex-1 overflow-hidden">
        <RunList />
      </div>
    </div>
  )
}
