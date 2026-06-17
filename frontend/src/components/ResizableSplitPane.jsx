import React, { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'

const SEPARATOR_PX = 10
const MIN_LEFT_PX  = 280
const MIN_RIGHT_PX = 320

export default function ResizableSplitPane({
  left,
  right,
  widthPercent,
  onWidthChange,
  className,
}) {
  const dragging = useRef(false)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef(null)
  const handleRef = useRef(null)

  const clampWidthPercent = useCallback((clientX) => {
    const el = containerRef.current
    if (!el) return widthPercent

    const rect = el.getBoundingClientRect()
    const usable = rect.width - SEPARATOR_PX
    if (usable <= 0) return widthPercent

    const rightPx = rect.right - clientX
    const minRight = Math.min(MIN_RIGHT_PX, usable * 0.15)
    const maxRight = usable - Math.min(MIN_LEFT_PX, usable * 0.85)
    const clampedRight = Math.max(minRight, Math.min(maxRight, rightPx))

    return (clampedRight / usable) * 100
  }, [widthPercent])

  const onPointerDown = useCallback((e) => {
    e.preventDefault()
    dragging.current = true
    setIsDragging(true)
    handleRef.current?.setPointerCapture(e.pointerId)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const onPointerMove = useCallback((e) => {
    if (!dragging.current) return
    onWidthChange(clampWidthPercent(e.clientX))
  }, [clampWidthPercent, onWidthChange])

  const endDrag = useCallback((e) => {
    if (!dragging.current) return
    dragging.current = false
    setIsDragging(false)
    if (e?.pointerId != null) {
      try { handleRef.current?.releasePointerCapture(e.pointerId) } catch { /* already released */ }
    }
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  useEffect(() => {
    if (!isDragging) return
    const move = (e) => onPointerMove(e)
    const up = (e) => endDrag(e)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
  }, [isDragging, onPointerMove, endDrag])

  useEffect(() => {
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [])

  const rightPct = Math.min(85, Math.max(15, widthPercent))
  const leftPct  = 100 - rightPct

  return (
    <>
      {isDragging && (
        <div
          className="fixed inset-0 z-[100] cursor-col-resize"
          style={{ userSelect: 'none', touchAction: 'none' }}
          aria-hidden="true"
        />
      )}

      <div
      ref={containerRef}
      className={clsx('w-full overflow-hidden', className)}
      style={{
        display: 'grid',
        gridTemplateColumns: `${leftPct}fr ${SEPARATOR_PX}px ${rightPct}fr`,
      }}
    >
      <div className="min-w-0 overflow-y-auto">
        {left}
      </div>

      <div
        ref={handleRef}
        role="separator"
        aria-orientation="vertical"
        aria-valuenow={Math.round(rightPct)}
        aria-valuemin={15}
        aria-valuemax={85}
        aria-label="Resize statement panel"
        onPointerDown={onPointerDown}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        className="relative z-20 cursor-col-resize touch-none select-none bg-border hover:bg-blue-400 active:bg-blue-500 transition-colors"
        style={{ touchAction: 'none' }}
      >
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-12 rounded-full bg-gray-300 dark:bg-slate-600 pointer-events-none" />
      </div>

      <div className="min-w-0 flex flex-col border-l border-border bg-card overflow-hidden">
        {right}
      </div>
    </div>
    </>
  )
}
