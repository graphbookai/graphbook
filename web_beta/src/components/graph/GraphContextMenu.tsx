import { useStore } from '@/store'
import { ContextMenu } from '@/components/shared/ContextMenu'
import { ContextMenuItem } from '@/components/shared/ContextMenuItem'
import { Network, LayoutGrid } from 'lucide-react'

interface GraphContextMenuProps {
  isOpen: boolean
  position: { x: number; y: number }
  onClose: () => void
}

export function GraphContextMenu({ isOpen, position, onClose }: GraphContextMenuProps) {
  const desktopViewMode = useStore(s => s.desktopViewMode)
  const setDesktopViewMode = useStore(s => s.setDesktopViewMode)

  return (
    <ContextMenu isOpen={isOpen} position={position} onClose={onClose}>
      <ContextMenuItem
        label="Graph View"
        icon={<Network className="w-4 h-4" />}
        checked={desktopViewMode === 'graph'}
        onClick={() => { setDesktopViewMode('graph'); onClose() }}
      />
      <ContextMenuItem
        label="Grid View"
        icon={<LayoutGrid className="w-4 h-4" />}
        checked={desktopViewMode === 'grid'}
        onClick={() => { setDesktopViewMode('grid'); onClose() }}
      />
    </ContextMenu>
  )
}
