/**
 * Charts.jsx
 * ----------
 * Theme-aware Recharts wrappers. Gridlines, axis ticks, cursor highlights
 * and dot strokes adapt to light/dark mode via useChartTheme().
 *
 * Data colors (blue/green/red/purple/amber) stay constant — they read on
 * both light and dark backgrounds and preserve the design system semantics.
 */
import React from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
  Area, AreaChart, LabelList, PieChart, Pie, Cell,
  ComposedChart,
} from 'recharts'
import useStore from '../store/useStore'

// ── Theme hook ───────────────────────────────────────────────────────────────
function useChartTheme() {
  const theme = useStore((s) => s.theme)
  const isDark = theme === 'dark'
  return {
    isDark,
    grid:    isDark ? '#1E293B' : '#F1F5F9',         // CartesianGrid stroke
    axis:    isDark ? '#94A3B8' : '#64748B',         // axis tick text
    label:   isDark ? '#94A3B8' : '#64748B',         // LabelList text
    cursor:  isDark ? 'rgba(148,163,184,0.08)' : '#F8FAFC',
    ref:     isDark ? '#475569' : '#CBD5E1',         // ReferenceLine
    dotStroke: isDark ? '#0E1629' : '#FFFFFF',       // dot border = card color
    legend:  isDark ? '#94A3B8' : '#64748B',         // legend text
    tooltipBg:     isDark ? '#020617' : '#0F172A',   // tooltip surface
    tooltipBorder: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.10)',
  }
}

// ── Statement sort helpers ───────────────────────────────────────────────────
const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function fmtMonthLabel(s) {
  if (s.statement_date) {
    const parts = s.statement_date.split('-')
    const m = parseInt(parts[1], 10)
    if (m >= 1 && m <= 12) return `${MONTH_NAMES[m - 1]} '${parts[0].slice(2)}`
  }
  return s.filename?.replace(/\.[^.]+$/, '').slice(0, 10) ?? ''
}

const MONTH_MAP = {
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6,
  july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
  jan: 1, feb: 2, mar: 3, apr: 4, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
}

function parseSortKey(s) {
  if (s.statement_date) return s.statement_date.slice(0, 7)
  const name = (s.filename ?? '').toLowerCase()
  const year  = (name.match(/\b(20\d{2})\b/) ?? [])[1] ?? '0000'
  for (const [word, num] of Object.entries(MONTH_MAP)) {
    if (name.includes(word)) return `${year}-${String(num).padStart(2, '0')}`
  }
  const mNum = (name.match(/\b(0?[1-9]|1[0-2])\b/) ?? [])[1]
  if (mNum) return `${year}-${mNum.padStart(2, '0')}`
  return '0000-00'
}

const sortDesc = (statements) => [...statements].sort((a, b) => parseSortKey(b).localeCompare(parseSortKey(a)))
const sortAsc  = (statements) => [...statements].sort((a, b) => parseSortKey(a).localeCompare(parseSortKey(b)))

// ── Formatters ───────────────────────────────────────────────────────────────
const fmtFull = (v) =>
  `$${Number(v ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const fmtK = (v) =>
  Math.abs(v) >= 1_000_000
    ? `$${(v / 1_000_000).toFixed(1)}M`
    : Math.abs(v) >= 1000
    ? `$${(v / 1000).toFixed(0)}k`
    : `$${v}`
const fmtPct   = (v) => `${Number(v ?? 0).toFixed(1)}%`
const fmtInt   = (v) => String(Math.round(v ?? 0))
const fmtRatio = (v) => `${Number(v ?? 0).toFixed(1)}×`

// ── Tooltip — themed wrapper ────────────────────────────────────────────────
function Tip({ active, payload, label, formatter = fmtFull, t }) {
  if (!active || !payload?.length) return null
  return (
    <div
      role="tooltip"
      className="text-white text-xs rounded-xl px-4 py-3 shadow-lg font-sans border"
      style={{ background: t.tooltipBg, borderColor: t.tooltipBorder }}
    >
      <p className="font-semibold text-slate-400 mb-2 font-mono tracking-wide">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 mb-0.5">
          <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-mono font-semibold ml-auto pl-4">{formatter(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

// ── Empty-state helper ──────────────────────────────────────────────────────
const empty = (msg = 'No statement data yet', cls = 'h-60') => (
  <div className={`flex items-center justify-center ${cls} text-sm text-text-muted font-sans text-center px-4`}>
    {msg}
  </div>
)

// ── Themed axis primitives ──────────────────────────────────────────────────
// NOTE: These must be PROP FACTORIES (not wrapper components) so that
// <XAxis> and <YAxis> remain direct children of the chart — Recharts
// detects axes by element.type and can't see through React component wrappers.
const gridProps  = (t) => ({ strokeDasharray: '3 3', stroke: t.grid, vertical: false })
const xAxisProps = (t) => ({
  dataKey: 'name',
  tick: { fontSize: 11, fill: t.axis, fontFamily: 'Inter, sans-serif' },
  axisLine: false, tickLine: false,
})
const yAxisProps = (t, formatter = fmtK, width = 54, allowDecimals = true) => ({
  tickFormatter: formatter, width, allowDecimals,
  tick: { fontSize: 11, fill: t.axis, fontFamily: 'Inter, sans-serif' },
  axisLine: false, tickLine: false,
})
const legendStyle = (t) => ({ fontSize: 11, color: t.legend, paddingBottom: 4, fontFamily: 'Inter, sans-serif' })
const labelStyle  = (t) => ({ fontSize: 9, fill: t.label, fontFamily: 'JetBrains Mono, monospace' })

// ── Charts ──────────────────────────────────────────────────────────────────
export function RevenueChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty()

  const data = sortAsc(statements).map((s) => ({
    name:            fmtMonthLabel(s),
    Credits:         s.credits         ?? 0,
    Debits:          s.debits          ?? 0,
    'Lender Debits': s.lender_debits   ?? 0,
  }))

  return (
    <div aria-label={`Revenue vs Debits bar chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }} barGap={3} barCategoryGap="28%">
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t)} />
          <Tooltip content={(p) => <Tip {...p} t={t} />} cursor={{ fill: t.cursor }} />
          <Legend wrapperStyle={legendStyle(t)} iconType="square" iconSize={8} />
          <Bar dataKey="Credits" fill="#2563EB" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Credits" position="top" formatter={fmtK} style={labelStyle(t)} />
          </Bar>
          <Bar dataKey="Debits" fill="#EF4444" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Debits" position="top" formatter={fmtK} style={labelStyle(t)} />
          </Bar>
          <Bar dataKey="Lender Debits" fill="#7C3AED" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Lender Debits" position="top" formatter={fmtK} style={labelStyle(t)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function CashFlowChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty()

  const data = sortAsc(statements).map((s) => ({
    name:        fmtMonthLabel(s),
    'Cash Flow': s.cash_flow ?? 0,
  }))

  return (
    <div aria-label={`Cash flow trend area chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="cfGradPos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#22C55E" stopOpacity={0.22} />
              <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t)} />
          <Tooltip content={(p) => <Tip {...p} t={t} />} />
          <ReferenceLine y={0} stroke={t.ref} strokeDasharray="4 4" />
          <Area
            type="monotone" dataKey="Cash Flow"
            stroke="#22C55E" strokeWidth={2.5} fill="url(#cfGradPos)"
            dot={{ r: 4, fill: '#22C55E', stroke: t.dotStroke, strokeWidth: 2 }}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DailyBalanceTrendChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty()

  const data = sortAsc(statements).map((s) => ({
    name:              fmtMonthLabel(s),
    'Avg Daily Balance': s.avg_daily_balance ?? 0,
  }))

  return (
    <div aria-label={`Daily balance trend area chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#2563EB" stopOpacity={0.22} />
              <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t)} />
          <Tooltip content={(p) => <Tip {...p} t={t} />} />
          <Area
            type="monotone" dataKey="Avg Daily Balance"
            stroke="#2563EB" strokeWidth={2.5} fill="url(#balGrad)"
            dot={{ r: 4, fill: '#2563EB', stroke: t.dotStroke, strokeWidth: 2 }}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function FinancialOverviewChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty()

  const data = sortAsc(statements).map((s) => ({
    name:                fmtMonthLabel(s),
    'Net Cash Flow':     s.cash_flow         ?? 0,
    'Lender Credits':    s.lender_credits     ?? 0,
    'Avg Daily Balance': s.avg_daily_balance  ?? 0,
  }))

  return (
    <div aria-label={`Financial overview line chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t)} />
          <Tooltip content={(p) => <Tip {...p} t={t} />} />
          <Legend wrapperStyle={legendStyle(t)} iconType="circle" iconSize={7} />
          <ReferenceLine y={0} stroke={t.ref} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="Net Cash Flow"     stroke="#22C55E" strokeWidth={2.5} dot={{ r: 4, fill: '#22C55E', stroke: t.dotStroke, strokeWidth: 2 }} activeDot={{ r: 6, strokeWidth: 2 }} />
          <Line type="monotone" dataKey="Lender Credits"    stroke="#7C3AED" strokeWidth={2.5} dot={{ r: 4, fill: '#7C3AED', stroke: t.dotStroke, strokeWidth: 2 }} activeDot={{ r: 6, strokeWidth: 2 }} />
          <Line type="monotone" dataKey="Avg Daily Balance" stroke="#2563EB" strokeWidth={2.5} strokeDasharray="5 3" dot={{ r: 4, fill: '#2563EB', stroke: t.dotStroke, strokeWidth: 2 }} activeDot={{ r: 6, strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function WithholdingRateChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty('No statement data yet', 'h-52')

  const data = sortAsc(statements).map((s) => ({
    name:               fmtMonthLabel(s),
    'Withholding Rate': s.withholding_rate ?? 0,
  }))

  return (
    <div aria-label={`Withholding rate trend across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="whGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#F59E0B" stopOpacity={0.22} />
              <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t, fmtPct, 42)} />
          <Tooltip content={(p) => <Tip {...p} formatter={fmtPct} t={t} />} />
          <Area
            type="monotone" dataKey="Withholding Rate"
            stroke="#F59E0B" strokeWidth={2.5} fill="url(#whGrad)"
            dot={{ r: 4, fill: '#F59E0B', stroke: t.dotStroke, strokeWidth: 2 }}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function NSFCountChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty('No statement data yet', 'h-52')

  const data = sortAsc(statements).map((s) => ({
    name:        fmtMonthLabel(s),
    'NSF Count': s.nsf_count ?? 0,
  }))

  return (
    <div aria-label={`NSF count bar chart across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }} barCategoryGap="36%">
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t, fmtInt, 32, false)} />
          <Tooltip content={(p) => <Tip {...p} formatter={fmtInt} t={t} />} cursor={{ fill: t.cursor }} />
          <Bar dataKey="NSF Count" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d['NSF Count'] > 0 ? '#EF4444' : (t.isDark ? '#334155' : '#CBD5E1')} />
            ))}
            <LabelList dataKey="NSF Count" position="top" formatter={fmtInt} style={labelStyle(t)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DebtLoadDonutChart({ totals }) {
  const t = useChartTheme()
  const lender   = Number(totals?.lender_debits ?? 0)
  const total    = Number(totals?.debits ?? 0)
  const organic  = Math.max(0, total - lender)

  if (total === 0) return empty('No statement data yet', 'h-52')

  const data = [
    { name: 'Lender Debits',  value: lender,  color: '#7C3AED' },
    { name: 'Organic Debits', value: organic, color: t.isDark ? '#334155' : '#CBD5E1' },
  ]

  const lenderPct = total > 0 ? ((lender / total) * 100).toFixed(1) : '0.0'

  return (
    <div aria-label={`Debt load donut: ${lenderPct}% lender debits`} className="flex flex-col items-center">
      <div className="relative w-[180px] h-[180px]">
        <PieChart width={180} height={180}>
          <Pie
            data={data} cx={90} cy={90}
            innerRadius={54} outerRadius={82}
            dataKey="value" startAngle={90} endAngle={-270} strokeWidth={0}
          >
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0]
              return (
                <div role="tooltip"
                     className="text-white text-xs rounded-xl px-4 py-3 shadow-lg font-sans border"
                     style={{ background: t.tooltipBg, borderColor: t.tooltipBorder }}>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-sm" style={{ background: p.payload.color }} />
                    <span className="text-slate-400">{p.name}:</span>
                    <span className="font-mono font-semibold ml-auto pl-4">{fmtFull(p.value)}</span>
                  </div>
                </div>
              )
            }}
          />
        </PieChart>
        <div
          className="absolute flex flex-col items-center pointer-events-none"
          style={{ top: 90, left: 90, transform: 'translate(-50%, -50%)' }}
        >
          <span className="font-mono text-[22px] font-bold text-text-primary leading-none">{lenderPct}%</span>
          <span className="text-[10px] text-text-muted mt-0.5">lender</span>
        </div>
      </div>

      <div className="flex gap-5 mt-3">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: d.color }} />
            <span className="text-[11px] text-text-muted font-medium">{d.name}</span>
            <span className="text-[11px] font-mono font-semibold text-text-primary">{fmtK(d.value)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function MoMRevenueChart({ statements }) {
  const t = useChartTheme()
  const sorted = sortAsc(statements ?? [])
  if (sorted.length < 2) return empty('Need at least 2 statements to show month-over-month change', 'h-52')

  const data = sorted.slice(1).map((s, i) => {
    const prev   = sorted[i]
    const change = prev.credits > 0
      ? Number(((s.credits - prev.credits) / prev.credits * 100).toFixed(1))
      : 0
    return {
      name: fmtMonthLabel(s),
      'MoM Change': change,
    }
  })

  return (
    <div aria-label={`Month-over-month revenue change across ${data.length} period(s)`}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }} barCategoryGap="36%">
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t, fmtPct, 62)} />
          <Tooltip content={(p) => <Tip {...p} formatter={fmtPct} t={t} />} cursor={{ fill: t.cursor }} />
          <ReferenceLine y={0} stroke={t.ref} strokeDasharray="4 4" />
          <Bar dataKey="MoM Change" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d['MoM Change'] >= 0 ? '#22C55E' : '#EF4444'} />
            ))}
            <LabelList dataKey="MoM Change" position="top" formatter={fmtPct} style={labelStyle(t)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function BalanceObligationChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty('No statement data yet', 'h-52')

  const data = sortAsc(statements).map((s) => {
    const bal = s.avg_daily_balance ?? 0
    const obl = s.lender_debits    ?? 0
    return {
      name:  fmtMonthLabel(s),
      'Balance / Obligation': obl > 0 ? Number(Math.min(bal / obl, 15).toFixed(2)) : null,
    }
  })

  return (
    <div aria-label={`Balance-to-obligation ratio across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t, fmtRatio, 42)} />
          <Tooltip content={(p) => <Tip {...p} formatter={(v) => v == null ? 'N/A' : fmtRatio(v)} t={t} />} />
          <ReferenceLine y={1} stroke="#EF4444" strokeDasharray="4 4"
            label={{ value: '1× min', position: 'insideTopRight', fontSize: 9, fill: '#EF4444' }} />
          <Line
            type="monotone" dataKey="Balance / Obligation"
            stroke={t.isDark ? '#475569' : '#CBD5E1'}
            strokeWidth={2.5} connectNulls={false}
            dot={(props) => {
              const { cx, cy, payload } = props
              const v = payload['Balance / Obligation']
              if (v == null) return <g />
              const color = v >= 2 ? '#22C55E' : v >= 1 ? '#F59E0B' : '#EF4444'
              return <circle cx={cx} cy={cy} r={5} fill={color} stroke={t.dotStroke} strokeWidth={2} />
            }}
            activeDot={(props) => {
              const { cx, cy, payload } = props
              const v = payload['Balance / Obligation']
              if (v == null) return <g />
              const color = v >= 2 ? '#22C55E' : v >= 1 ? '#F59E0B' : '#EF4444'
              return <circle cx={cx} cy={cy} r={7} fill={color} stroke={t.dotStroke} strokeWidth={2.5} />
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function LenderInOutChart({ statements }) {
  const t = useChartTheme()
  if (!statements?.length) return empty('No statement data yet', 'h-52')

  const data = sortAsc(statements).map((s) => ({
    name:             fmtMonthLabel(s),
    'Lender Credits': s.lender_credits ?? 0,
    'Lender Debits':  s.lender_debits  ?? 0,
  }))

  return (
    <div aria-label={`Lender credits vs debits across ${data.length} statement(s)`}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 16, right: 4, left: 0, bottom: 0 }} barGap={3} barCategoryGap="28%">
          <CartesianGrid {...gridProps(t)} /><XAxis {...xAxisProps(t)} /><YAxis {...yAxisProps(t)} />
          <Tooltip content={(p) => <Tip {...p} t={t} />} cursor={{ fill: t.cursor }} />
          <Legend wrapperStyle={legendStyle(t)} iconType="square" iconSize={8} />
          <Bar dataKey="Lender Credits" fill="#10B981" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Lender Credits" position="top" formatter={fmtK} style={labelStyle(t)} />
          </Bar>
          <Bar dataKey="Lender Debits" fill="#7C3AED" radius={[4, 4, 0, 0]}>
            <LabelList dataKey="Lender Debits" position="top" formatter={fmtK} style={labelStyle(t)} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ForecastSparkline({ statements, predicted, nextMonthLabel }) {
  const t = useChartTheme()
  if (!statements?.length) return null

  const label = (s) => fmtMonthLabel(s)

  const sorted = [...statements].sort((a, b) =>
    (a.statement_date ?? a.filename ?? '').localeCompare(b.statement_date ?? b.filename ?? ''))

  const data = sorted.map((s, i) => ({
    name:     label(s),
    Revenue:  Number(s.credits ?? 0),
    Forecast: i === sorted.length - 1 ? Number(s.credits ?? 0) : null,
  }))
  data.push({ name: nextMonthLabel, Revenue: null, Forecast: predicted })

  return (
    <ResponsiveContainer width="100%" height={90}>
      <ComposedChart data={data} margin={{ top: 6, right: 6, left: 6, bottom: 0 }}>
        <defs>
          <linearGradient id="fcastGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#2563EB" stopOpacity={0.18} />
            <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone" dataKey="Revenue"
          stroke="#2563EB" strokeWidth={2} fill="url(#fcastGrad)"
          dot={false} connectNulls={false}
        />
        <Line
          type="monotone" dataKey="Forecast"
          stroke="#2563EB" strokeWidth={2} strokeDasharray="5 3"
          connectNulls
          dot={(props) => {
            const { cx, cy, index } = props
            if (index !== data.length - 1) return <g />
            return <circle cx={cx} cy={cy} r={5} fill={t.dotStroke} stroke="#2563EB" strokeWidth={2.5} />
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
