import React from 'react'
import clsx from 'clsx'

// Accent bar + icon bg mapping (design system: fintech palette)
const themes = {
  blue:   { bar: 'bg-primary',  icon: 'bg-blue-50     dark:bg-blue-500/15   text-primary    dark:text-blue-300',  val: 'text-text-primary' },
  green:  { bar: 'bg-accent',   icon: 'bg-green-light dark:bg-green-500/15  text-green-600  dark:text-green-300', val: 'text-green-600 dark:text-green-400' },
  red:    { bar: 'bg-danger',   icon: 'bg-red-light   dark:bg-red-500/15    text-danger     dark:text-red-300',   val: 'text-danger dark:text-red-400' },
  amber:  { bar: 'bg-warning',  icon: 'bg-amber-light dark:bg-amber-500/15  text-warning    dark:text-amber-300', val: 'text-warning dark:text-amber-400' },
  purple: { bar: 'bg-purple',   icon: 'bg-purple-light dark:bg-purple-500/15 text-purple   dark:text-purple-300', val: 'text-text-primary' },
  none:   { bar: 'bg-border',   icon: 'bg-gray-100    dark:bg-white/10      text-gray-500   dark:text-slate-300', val: 'text-text-primary' },
}

export default function MetricCard({ label, value, sub, icon: Icon, accent = 'none', badge }) {
  const t = themes[accent] ?? themes.none

  return (
    <div className={clsx(
      'relative bg-card border border-border rounded-2xl overflow-hidden shadow-xs',
      'transition-all duration-base cursor-default',
      'hover:shadow-md hover:-translate-y-0.5 hover:border-slate-300 dark:hover:border-white/15',
      'group'
    )}>
      {/* Coloured top accent bar */}
      <div className={clsx('h-0.5 w-full', t.bar)} />

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between mb-4">
          {/* Label: uppercase tracking, 11px — font-sans */}
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.6px] text-text-muted leading-none">
            {label}
          </p>
          <div className="flex items-center gap-2">
            {badge && (
              <span className={clsx('badge', `badge-${accent === 'none' ? 'gray' : accent}`)}>
                {badge}
              </span>
            )}
            {Icon && (
              <div className={clsx(
                'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0',
                'transition-transform duration-fast group-hover:scale-105',
                t.icon
              )}>
                <Icon size={14} strokeWidth={2} aria-hidden="true" />
              </div>
            )}
          </div>
        </div>

        {/* Value: JetBrains Mono — tabular nums prevent layout shift (ux-guidelines: number-tabular) */}
        <p className={clsx(
          'font-mono tabular-nums text-[26px] font-semibold leading-none mb-2 tracking-tight',
          t.val
        )}>
          {value}
        </p>

        {/* Sub: font-sans, text-muted */}
        {sub && (
          <p className="font-sans text-[11px] text-text-muted font-medium leading-snug">
            {sub}
          </p>
        )}
      </div>
    </div>
  )
}
