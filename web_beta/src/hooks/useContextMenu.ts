import { useCallback, useRef, useState } from 'react'

interface Position {
  x: number
  y: number
}

interface ContextMenuState {
  isOpen: boolean
  position: Position
  open: (e: React.MouseEvent | React.TouchEvent) => void
  close: () => void
  handlers: {
    onContextMenu: (e: React.MouseEvent) => void
    onTouchStart: (e: React.TouchEvent) => void
    onTouchEnd: () => void
    onTouchMove: () => void
  }
}

const LONG_PRESS_MS = 500

export function useContextMenu(): ContextMenuState {
  const [isOpen, setIsOpen] = useState(false)
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const touchPosRef = useRef<Position>({ x: 0, y: 0 })

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const open = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault()
    if ('clientX' in e) {
      setPosition({ x: e.clientX, y: e.clientY })
    } else if (e.touches.length > 0) {
      const touch = e.touches[0]
      setPosition({ x: touch.clientX, y: touch.clientY })
    }
    setIsOpen(true)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
  }, [])

  const onContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      setPosition({ x: e.clientX, y: e.clientY })
      setIsOpen(true)
    },
    [],
  )

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length !== 1) return
      const touch = e.touches[0]
      touchPosRef.current = { x: touch.clientX, y: touch.clientY }
      clearTimer()
      timerRef.current = setTimeout(() => {
        setPosition(touchPosRef.current)
        setIsOpen(true)
      }, LONG_PRESS_MS)
    },
    [clearTimer],
  )

  const onTouchEnd = useCallback(() => {
    clearTimer()
  }, [clearTimer])

  const onTouchMove = useCallback(() => {
    clearTimer()
  }, [clearTimer])

  return {
    isOpen,
    position,
    open,
    close,
    handlers: {
      onContextMenu,
      onTouchStart,
      onTouchEnd,
      onTouchMove,
    },
  }
}
