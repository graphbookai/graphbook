import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'motion/react'

interface ContextMenuProps {
  isOpen: boolean
  position: { x: number; y: number }
  onClose: () => void
  children: React.ReactNode
}

export function ContextMenu({ isOpen, position, onClose, children }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)
  const [adjusted, setAdjusted] = useState(position)

  useEffect(() => {
    if (!isOpen) return
    // Start with the raw position, then clamp after measuring
    setAdjusted(position)
  }, [isOpen, position])

  useEffect(() => {
    if (!isOpen) return
    // Measure and clamp after the menu has rendered
    const frame = requestAnimationFrame(() => {
      const el = menuRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const x = Math.min(position.x, window.innerWidth - rect.width - 4)
      const y = Math.min(position.y, window.innerHeight - rect.height - 4)
      setAdjusted({ x: Math.max(0, x), y: Math.max(0, y) })
    })
    return () => cancelAnimationFrame(frame)
  }, [isOpen, position])

  useEffect(() => {
    if (!isOpen) return
    const handleMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        // Don't close if clicking inside a Radix popover spawned by a menu item
        const target = e.target as Element
        if (target.closest?.('[data-radix-popper-content-wrapper]')) return
        onClose()
      }
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleMouseDown, true)
    document.addEventListener('pointerdown', handleMouseDown, true)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown, true)
      document.removeEventListener('pointerdown', handleMouseDown, true)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, onClose])

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          ref={menuRef}
          role="menu"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.1 }}
          className="bg-card border border-border rounded-lg shadow-lg py-1 min-w-[180px] z-50"
          style={{
            position: 'fixed',
            left: adjusted.x,
            top: adjusted.y,
          }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  )
}
