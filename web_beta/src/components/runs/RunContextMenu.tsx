import { useCallback, useState } from 'react'
import { CheckSquare, Square, GitCompare, Palette } from 'lucide-react'
import { useStore } from '@/store'
import { ContextMenu } from '@/components/shared/ContextMenu'
import { ContextMenuItem } from '@/components/shared/ContextMenuItem'
import { ColorPicker } from '@/components/shared/ColorPicker'

interface RunContextMenuProps {
  runId: string
  isOpen: boolean
  position: { x: number; y: number }
  onClose: () => void
}

export function RunContextMenu({ runId, isOpen, position, onClose }: RunContextMenuProps) {
  const selectedForCompare = useStore(s => s.selectedForCompare)
  const toggleSelectForCompare = useStore(s => s.toggleSelectForCompare)
  const createComparisonGroup = useStore(s => s.createComparisonGroup)
  const runColor = useStore(s => s.runColors.get(runId))
  const getOrAssignRunColor = useStore(s => s.getOrAssignRunColor)
  const setRunColor = useStore(s => s.setRunColor)

  const [colorPickerOpen, setColorPickerOpen] = useState(false)

  const isSelected = selectedForCompare.has(runId)

  const wouldBeSelected = isSelected
    ? selectedForCompare.size
    : selectedForCompare.size + 1

  const handleToggleSelect = useCallback(() => {
    toggleSelectForCompare(runId)
    onClose()
  }, [runId, toggleSelectForCompare, onClose])

  const handleCompare = useCallback(() => {
    const ids = new Set(selectedForCompare)
    if (!ids.has(runId)) {
      ids.add(runId)
    }
    createComparisonGroup([...ids])
    onClose()
  }, [runId, selectedForCompare, createComparisonGroup, onClose])

  const handleColorChange = useCallback((color: string) => {
    setRunColor(runId, color)
  }, [runId, setRunColor])

  const handleOpenColorPicker = useCallback(() => {
    onClose()
    // Open the standalone color picker after the menu has closed
    requestAnimationFrame(() => setColorPickerOpen(true))
  }, [onClose])

  const currentColor = runColor ?? getOrAssignRunColor(runId)

  return (
    <>
      <ContextMenu isOpen={isOpen} position={position} onClose={onClose}>
        <ContextMenuItem
          label="Select for Compare"
          icon={isSelected ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
          onClick={handleToggleSelect}
          checked={isSelected}
        />
        <ContextMenuItem
          label="Compare with Selected"
          icon={<GitCompare className="w-4 h-4" />}
          onClick={handleCompare}
          disabled={wouldBeSelected < 2}
        />
        <ContextMenuItem
          label="Change Color"
          icon={<Palette className="w-4 h-4" />}
          onClick={handleOpenColorPicker}
        />
      </ContextMenu>

      {/* ColorPicker rendered outside the ContextMenu so it survives the menu closing */}
      <ColorPicker
        color={currentColor}
        onChange={handleColorChange}
        open={colorPickerOpen}
        onOpenChange={setColorPickerOpen}
      >
        {/* Invisible anchor positioned at the context menu location */}
        <span
          style={{ position: 'fixed', left: position.x, top: position.y, width: 1, height: 1 }}
        />
      </ColorPicker>
    </>
  )
}
