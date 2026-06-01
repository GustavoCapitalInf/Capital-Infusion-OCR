import React, { useEffect } from 'react'
import { CheckCircle2, XCircle, X } from 'lucide-react'
import clsx from 'clsx'

/**
 * Toast — auto-dismisses after `duration` ms (default 4 s).
 * Props:
 *   message  string
 *   type     'success' | 'error'
 *   onClose  () => void
 *   duration number (ms)
 */
export default function Toast({ message, type = 'success', onClose, duration = 4000 }) {
  useEffect(() => {
    const t = setTimeout(onClose, duration)
    return () => clearTimeout(t)
  }, [onClose, duration])

  const isSuccess = type === 'success'

  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        'fixed bottom-6 right-6 z-50 flex items-start gap-3 px-4 py-3.5',
        'rounded-2xl border shadow-lg min-w-[280px] max-w-sm animate-slide-up',
        isSuccess
          ? 'bg-white border-green-border'
          : 'bg-white border-red-border'
      )}
    >
      {/* Icon */}
      <div className={clsx(
        'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0',
        isSuccess ? 'bg-green-light' : 'bg-red-light'
      )}>
        {isSuccess
          ? <CheckCircle2 size={16} className="text-green" strokeWidth={2} />
          : <XCircle     size={16} className="text-red"   strokeWidth={2} />}
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <p className="font-sans text-[13px] font-semibold text-text-primary leading-tight">
          {isSuccess ? 'Sent to Lender App' : 'Lender App Notification Failed'}
        </p>
        <p className="font-sans text-[11px] text-text-muted mt-0.5 leading-snug">
          {message}
        </p>
      </div>

      {/* Dismiss */}
      <button
        onClick={onClose}
        aria-label="Dismiss notification"
        className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center
                   text-text-muted hover:text-text-primary hover:bg-gray-100 transition-colors"
      >
        <X size={11} />
      </button>

      {/* Progress bar */}
      <div className={clsx(
        'absolute bottom-0 left-0 h-0.5 rounded-b-2xl',
        isSuccess ? 'bg-green' : 'bg-red'
      )}
        style={{ animation: `shrink ${duration}ms linear forwards` }}
      />

      <style>{`
        @keyframes shrink {
          from { width: 100%; }
          to   { width: 0%; }
        }
      `}</style>
    </div>
  )
}
