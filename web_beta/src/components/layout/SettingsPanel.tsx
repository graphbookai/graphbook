import { Settings, Moon, Sun, Map, Gamepad2, FoldVertical, GripHorizontal, EyeOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useStore } from '@/store'

export function SettingsPanel() {
  const settings = useStore(s => s.settings)
  const updateSetting = useStore(s => s.updateSetting)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" title="Settings">
          <Settings className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-60" align="end">
        <div className="space-y-4">
          <h4 className="text-sm font-medium">Settings</h4>

          {/* Theme */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              {settings.theme === 'dark' ? (
                <Moon className="h-3.5 w-3.5 text-muted-foreground" />
              ) : (
                <Sun className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              <span>Dark mode</span>
            </div>
            <Switch
              checked={settings.theme === 'dark'}
              onCheckedChange={v => updateSetting('theme', v ? 'dark' : 'light')}
            />
          </div>

          {/* Show minimap */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <Map className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Show minimap</span>
            </div>
            <Switch
              checked={settings.showMinimap}
              onCheckedChange={v => updateSetting('showMinimap', v)}
            />
          </div>

          {/* Show controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <Gamepad2 className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Show controls</span>
            </div>
            <Switch
              checked={settings.showControls}
              onCheckedChange={v => updateSetting('showControls', v)}
            />
          </div>

          {/* Collapse nodes by default */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <FoldVertical className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Nodes collapsed by default</span>
            </div>
            <Switch
              checked={settings.collapseNodesByDefault}
              onCheckedChange={v => updateSetting('collapseNodesByDefault', v)}
            />
          </div>

          {/* Hide tabs on drag */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <GripHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Hide tabs on drag</span>
            </div>
            <Switch
              checked={settings.hideTabsOnDrag}
              onCheckedChange={v => updateSetting('hideTabsOnDrag', v)}
            />
          </div>

          {/* Hide uncalled functions */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Hide uncalled functions</span>
            </div>
            <Switch
              checked={settings.hideUncalledFunctions}
              onCheckedChange={v => updateSetting('hideUncalledFunctions', v)}
            />
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
