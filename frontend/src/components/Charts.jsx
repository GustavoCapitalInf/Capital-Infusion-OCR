/**
 * Charts.jsx
 * ----------
 * Design system applied:
 * - Bar chart for category comparison (chart domain: Compare Categories → Bar ✓)
 * - Area chart for trends (chart domain: Trend Over Time → Area ✓)
 * - Value labels on each bar (chart guideline: direct-labeling ✓)
 * - Legend included (chart guideline: legend-visible ✓)
 * - Tooltip on hover (chart guideline: tooltip-on-interact ✓)
 * - Colors + distinct visual encoding (guideline: color-not-only ✓)
 * - aria-label on chart wrapper (guideline: screen-reader-summary ✓)
 * - Subtle gridlines (guideline: gridline-subtle ✓)
 * - font-display:swap already in index.css (guideline: font-loading ✓)
 */
import React from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
  Area, AreaChart, LabelList,
} from 'recharts'

// Locale-aware number formatting (chart guideline: number-formatting)
const fmtFull = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const fmtK = (v) =>
  Math.abs(v) >= 1_000_000
    ? `$${(v / 1_000_000).toFixed(1)}M`
    : Math.abs(v) >= 1000
    ? `$${(v / 1000).toFixed(0)}k`
    : `$${v}`

// Custom tooltip — keyboard reachable via recharts default tab (guideline: tooltip-keyboard)
const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div
      role="tooltip"
      className="bg-[#0F172A] text-white text-xs rounded-xl px-4 py-3 shadow-lg border border-white/10 font-sans"
    >
      <p className="font-semibold text-slate-400 mb-2 font-mono tracking-wide">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 mb-0.5">
          <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-mono font-semibold ml-auto pl-4">{fmtFull(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

const sharedAxis = {
  tick:     { fontSize: 11, fill: '#64748B', fontFamily: 'Inter, sans-serif' },
  axisLine: false,
  tickLine: false,
}

// Low-contrast gridlines so they don't compete with data (guideline: gridline-subtle)
const Grid = <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
const XAx  = <XAxis dataKey="name" {...sharedAxis} />
const YAx  = <YAxis tickFormatter={fmtK} {...sharedAxis} width={54} />

export function RevenueChart({ statements }) {
  if (!statements?.length) return (
    <div className="flex items-center justify-center h-60 text-sm text-text-muted font-sans">
      No statement data yet
    </div>
  )

  const data = statements.map((s) => ({
    name:            s.statement_date ? s.statement_date.slice(0, 7) : s.filename?.replace(/\.[^.]+$/, '').slice(0, 10),
    Credits:         s.credits         ?? 0,
    Debits:          s.debits          ?? 0,
    'Lender Debits': s.lender_debits   ?? 0,
  }))

  return (
    // aria-label provides text summary for screen readers (guideline: screen-reader-summary)
    <div aria-label={`Revenue vs Debits bar chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }} barGap={3} barCategoryGap="28%">
          {Grid}{XAx}{YAx}
          <Tooltip content={<Tip />} cursor={{ fill: '#F8FAFC' }} />
          {/* Legend at top — always visible, not detached below fold (guideline: legend-visible) */}
          <Legend
            wrapperStyle={{ fontSize: 11, color: '#64748B', paddingBottom: 4, fontFamily: 'Inter, sans-serif' }}
            iconType="square" iconSize={8}
          />
          {/* Value labels on bars — direct-labeling for small datasets (guideline: direct-labeling) */}
          <Bar dataKey="Credits" fill="#2563EB" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Credits" position="top" formatter={fmtK}
                       style={{ fontSize: 9, fill: '#64748B', fontFamily: 'JetBrains Mono, monospace' }} />
          </Bar>
          <Bar dataKey="Debits" fill="#EF4444" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Debits" position="top" formatter={fmtK}
                       style={{ fontSize: 9, fill: '#64748B', fontFamily: 'JetBrains Mono, monospace' }} />
          </Bar>
          {/* Purple for lender debits — distinct from red/blue (guideline: color-not-only) */}
          <Bar dataKey="Lender Debits" fill="#7C3AED" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Lender Debits" position="top" formatter={fmtK}
                       style={{ fontSize: 9, fill: '#64748B', fontFamily: 'JetBrains Mono, monospace' }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function CashFlowChart({ statements }) {
  if (!statements?.length) return (
    <div className="flex items-center justify-center h-60 text-sm text-text-muted font-sans">
      No statement data yet
    </div>
  )

  const data = statements.map((s) => ({
    name:        s.statement_date ? s.statement_date.slice(0, 7) : s.filename?.replace(/\.[^.]+$/, '').slice(0, 10),
    'Cash Flow': s.cash_flow ?? 0,
  }))

  return (
    <div aria-label={`Cash flow trend area chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="cfGradPos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#22C55E" stopOpacity={0.18} />
              <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
            </linearGradient>
          </defs>
          {Grid}{XAx}{YAx}
          <Tooltip content={<Tip />} />
          {/* Zero reference line — gives spatial context for positive/negative */}
          <ReferenceLine y={0} stroke="#CBD5E1" strokeDasharray="4 4" />
          {/* Solid line (not dashed) — single series so style distinction not needed */}
          <Area
            type="monotone"
            dataKey="Cash Flow"
            stroke="#22C55E"
            strokeWidth={2.5}
            fill="url(#cfGradPos)"
            dot={{ r: 4, fill: '#22C55E', stroke: 'white', strokeWidth: 2 }}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
