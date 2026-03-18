import * as Popover from '@radix-ui/react-popover'
import { RUN_COLOR_PALETTE } from '@/lib/colors'
import { cn } from '@/lib/utils'

interface ColorPickerProps {
  color: string
  onChange: (color: string) => void
  className?: string
  children?: React.ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function ColorPicker({ color, onChange, className, children, open, onOpenChange }: ColorPickerProps) {
  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>
        {children ?? (
          <button
            className={cn(
              'w-4 h-4 rounded-full border border-white/20 shrink-0 cursor-pointer',
              className,
            )}
            style={{ backgroundColor: color }}
            aria-label="Pick run color"
          />
        )}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="right"
          sideOffset={8}
          className="z-[60] rounded-lg border border-border bg-popover p-2 shadow-md"
        >
          <div className="grid grid-cols-4 gap-1.5">
            {RUN_COLOR_PALETTE.map(c => (
              <button
                key={c}
                className={cn(
                  'w-5 h-5 rounded-full border cursor-pointer transition-transform hover:scale-110',
                  c === color ? 'border-white ring-1 ring-white/50' : 'border-white/20',
                )}
                style={{ backgroundColor: c }}
                onClick={() => onChange(c)}
                aria-label={`Color ${c}`}
              />
            ))}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <label className="text-xs text-muted-foreground">Custom</label>
            <input
              type="color"
              value={color}
              onChange={e => onChange(e.target.value)}
              className="w-6 h-6 cursor-pointer border-0 bg-transparent p-0"
            />
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
