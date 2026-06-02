import React from 'react'
import { Sun, Moon } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store/useStore'

export default function ThemeToggle() {
  const theme = useStore((s) => s.theme)
  const toggleTheme = useStore((s) => s.toggleTheme)
  const isDark = theme === 'dark'

  return (
    <button
      onClick={toggleTheme}
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={clsx(
        'group relative inline-flex items-center h-7 w-[58px] rounded-full',
        'border transition-all duration-300 ease-out-expo cursor-pointer select-none',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2',
        'focus-visible:ring-offset-card',
        isDark
          ? 'bg-[#0E1629] border-white/10 hover:border-white/20'
          : 'bg-slate-100 border-border hover:border-slate-300'
      )}
    >
      {/* Track icons — both visible, dimmed on the opposite side */}
      <Sun
        size={11}
        strokeWidth={2.2}
        aria-hidden="true"
        className={clsx(
          'absolute left-2 transition-opacity duration-200',
          isDark ? 'text-slate-500 opacity-50' : 'text-amber-500 opacity-100'
        )}
      />
      <Moon
        size={11}
        strokeWidth={2.2}
        aria-hidden="true"
        className={clsx(
          'absolute right-2 transition-opacity duration-200',
          isDark ? 'text-blue-300 opacity-100' : 'text-slate-400 opacity-50'
        )}
      />

      {/* Sliding thumb */}
      <span
        className={clsx(
          'pointer-events-none relative z-10 flex items-center justify-center',
          'h-5 w-5 rounded-full shadow-md',
          'transition-transform duration-300 ease-out-expo',
          isDark
            ? 'translate-x-[34px] bg-gradient-to-br from-slate-200 to-slate-300'
            : 'translate-x-[3px] bg-gradient-to-br from-white to-slate-100'
        )}
      >
        {isDark
          ? <Moon size={10} strokeWidth={2.2} className="text-slate-700" />
          : <Sun  size={10} strokeWidth={2.2} className="text-amber-500" />}
      </span>
    </button>
  )
}
