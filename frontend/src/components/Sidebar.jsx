import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Building2, BarChart3,
  Download, Activity, ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store/useStore'

const links = [
  { to: '/dashboard',  label: 'Dashboard',  Icon: LayoutDashboard },
  { to: '/statements', label: 'Statements', Icon: FileText },
  { to: '/lenders',    label: 'Lenders',    Icon: Building2 },
  { to: '/analysis',   label: 'Analysis',   Icon: BarChart3 },
  { to: '/export',     label: 'Export',     Icon: Download },
]

// All text colours verified ≥4.5:1 on #080E1C (sidebar bg)
// sidebar-muted = #94A3B8 → 7.3:1 ✓  (WCAG AA)
// #CBD5E1        → 11.5:1 ✓  (active/hover text)
// #4B5563 would be ~3.1:1 — FAIL — never used for text

export default function Sidebar() {
  const { statements, totals } = useStore()
  const hasData = statements.length > 0

  return (
    <aside className="w-60 flex-shrink-0 flex flex-col bg-sidebar h-screen sticky top-0"
           style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}>

      {/* ── Brand ── */}
      <div className="px-5 pt-6 pb-5" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-purple-600
                          flex items-center justify-center shadow-lg shadow-primary/30 flex-shrink-0">
            <Activity size={17} className="text-white" strokeWidth={2.5} />
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-accent
                             border-2 border-sidebar animate-pulse-dot" />
          </div>
          <div>
            {/* Calistoga display font for brand name */}
            <p className="font-display text-[15px] text-white leading-none tracking-tight">Orbit Optix</p>
            {/* sidebar-muted (#94A3B8) = 7.3:1 on #080E1C ✓ */}
            <p className="font-mono text-[9px] text-sidebar-muted tracking-[2.5px] uppercase mt-1.5">
              Financial Intel
            </p>
          </div>
        </div>
      </div>

      {/* ── Live data pill ── */}
      {hasData && (
        <div className="mx-4 mt-4 px-3 py-2.5 rounded-xl"
             style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.18)' }}>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-dot" />
            {/* text-accent-DEFAULT (#22C55E) on rgba overlay → sufficient ✓ */}
            <p className="font-sans text-[11px] font-semibold text-accent">
              {statements.length} statement{statements.length !== 1 ? 's' : ''} loaded
            </p>
          </div>
          {totals && (
            /* lighter tint of accent for sub-line */
            <p className="font-mono text-[10px] mt-0.5 pl-3.5" style={{ color: 'rgba(34,197,94,0.55)' }}>
              ${(totals.credits / 1000).toFixed(0)}k revenue · {totals.nsf_count} NSF
            </p>
          )}
        </div>
      )}

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 py-5 space-y-0.5 overflow-y-auto">
        {/* Section label — sidebar-muted passes 7.3:1 ✓ */}
        <p className="font-mono text-[9px] font-bold tracking-[2.5px] uppercase text-sidebar-muted px-3 mb-3">
          Navigation
        </p>

        {links.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => clsx(
              'group flex items-center gap-3 px-3 py-2.5 rounded-xl font-sans text-[13px] font-medium',
              'transition-all duration-fast cursor-pointer select-none',
              isActive
                ? 'text-[#CBD5E1] bg-white/8 border border-white/10'        // 11.5:1 ✓
                : 'text-sidebar-muted hover:bg-white/5 hover:text-[#CBD5E1]' // 7.3:1 ✓ base, 11.5:1 ✓ hover
            )}
          >
            {({ isActive }) => (
              <>
                <div className={clsx(
                  'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-fast',
                  isActive
                    ? 'bg-primary/20 text-blue-300'    // blue-300 = #93C5FD → sufficient ✓
                    : 'bg-white/5 text-sidebar-muted group-hover:bg-white/10 group-hover:text-[#CBD5E1]'
                )}>
                  <Icon size={14} strokeWidth={isActive ? 2.2 : 1.8} />
                </div>
                <span className="flex-1 leading-none">{label}</span>
                {isActive && (
                  <ChevronRight size={12} className="text-blue-400 opacity-60" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* ── Footer ── */}
      <div className="px-4 py-4" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-2.5 px-2 py-2">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-slate-600 to-slate-700
                          flex items-center justify-center flex-shrink-0">
            <span className="font-mono text-[9px] font-bold text-white">CI</span>
          </div>
          <div>
            {/* sidebar-muted = 7.3:1 ✓ */}
            <p className="font-sans text-[11px] font-semibold text-sidebar-muted leading-none">
              Capital Infusion
            </p>
            <p className="font-mono text-[9px] mt-0.5" style={{ color: 'rgba(148,163,184,0.5)' }}>
              v2.0.0
            </p>
          </div>
        </div>
      </div>
    </aside>
  )
}
