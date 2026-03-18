import type { ReactNode } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ContextMenuItemProps {
  label: string
  icon?: ReactNode
  onClick: () => void
  disabled?: boolean
  checked?: boolean
}

export function ContextMenuItem({ label, icon, onClick, disabled, checked }: ContextMenuItemProps) {
  return (
    <button
      role="menuitem"
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      className={cn(
        'px-3 py-1.5 text-sm hover:bg-accent/50 transition-colors w-full text-left flex items-center gap-2',
        disabled && 'opacity-50 cursor-not-allowed pointer-events-none',
      )}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="flex-1">{label}</span>
      {checked && <Check className="w-4 h-4 shrink-0" />}
    </button>
  )
}
