import React from 'react'
import useStore from '../store/useStore'
import { ShieldCheck, ShieldAlert, Shield, HelpCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import clsx from 'clsx'
import { RevenueChart, CashFlowChart, DailyBalanceTrendChart, FinancialOverviewChart, WithholdingRateChart, NSFCountChart, DebtLoadDonutChart, MoMRevenueChart, BalanceObligationChart, LenderInOutChart, ForecastSparkline } from '../components/Charts'

const RISK_CONFIG = {
  'Low Risk':    { icon: ShieldCheck, bg: 'bg-green-light dark:bg-green-500/15', border: 'border-green-border dark:border-green-500/30', text: 'text-green dark:text-green-300', bar: 'bg-green' },
  'Medium Risk': { icon: Shield,      bg: 'bg-amber-light dark:bg-amber-500/15', border: 'border-amber-border dark:border-amber-500/30', text: 'text-amber dark:text-amber-300', bar: 'bg-amber' },
  'High Risk':   { icon: ShieldAlert, bg: 'bg-red-light   dark:bg-red-500/15',   border: 'border-red-border   dark:border-red-500/30',   text: 'text-red   dark:text-red-300',   bar: 'bg-red' },
}

const $fmt = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`

function getNextMonthLabel(statementDate) {
  if (!statementDate) return 'Next Month'
  const [year, month] = statementDate.split('-').map(Number)
  const next     = month === 12 ? 1 : month + 1
  const nextYear = month === 12 ? year + 1 : year
  return `${nextYear}-${String(next).padStart(2, '0')}`
}

function forecastRevenue(statements) {
  if (!statements?.length) return null
  const sorted = [...statements].sort((a, b) =>
    (a.statement_date ?? a.filename ?? '').localeCompare(b.statement_date ?? b.filename ?? ''))
  const points = sorted.map((s, i) => ({ x: i, y: Number(s.credits ?? 0) }))
  const n = points.length

  let predicted
  if (n === 1) {
    predicted = points[0].y
  } else {
    const sumX  = points.reduce((s, p) => s + p.x, 0)
    const sumY  = points.reduce((s, p) => s + p.y, 0)
    const sumXY = points.reduce((s, p) => s + p.x * p.y, 0)
    const sumX2 = points.reduce((s, p) => s + p.x * p.x, 0)
    const denom = n * sumX2 - sumX * sumX
    if (denom === 0) {
      predicted = sumY / n
    } else {
      const m = (n * sumXY - sumX * sumY) / denom
      const b = (sumY - m * sumX) / n
      predicted = Math.max(0, m * n + b)
    }
  }

  const lastRevenue = points[n - 1].y
  const delta       = predicted - lastRevenue
  const deltaPct    = lastRevenue > 0 ? (delta / lastRevenue) * 100 : 0
  const confidence  = n >= 6 ? 'High' : n >= 3 ? 'Medium' : 'Low'
  const nextMonthLabel = getNextMonthLabel(sorted[n - 1].statement_date)

  return { predicted, delta, deltaPct, confidence, nextMonthLabel, n }
}

function InfoTooltip({ children }) {
  return (
    <div className="relative group flex items-center">
      <HelpCircle size={14} className="text-text-muted cursor-help" strokeWidth={1.8} />
      <div className="absolute bottom-full right-0 mb-2 w-72 bg-[#0F172A] dark:bg-[#020617] text-white text-xs rounded-xl px-4 py-3 shadow-lg border border-white/10 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150 z-50">
        {children}
      </div>
    </div>
  )
}

export default function Analysis() {
  const { risk, statements, totals } = useStore()
  const cfg  = risk ? (RISK_CONFIG[risk.level] ?? RISK_CONFIG['Low Risk']) : null
  const Icon = cfg?.icon ?? Shield

  const fc              = statements?.length > 0 ? forecastRevenue(statements) : null
  const TrendIcon       = !fc ? Minus : fc.deltaPct > 1 ? TrendingUp : fc.deltaPct < -1 ? TrendingDown : Minus
  const trendColor      = !fc ? 'text-text-muted' : fc.deltaPct > 1 ? 'text-green dark:text-green-400' : fc.deltaPct < -1 ? 'text-red dark:text-red-400' : 'text-text-muted'
  const confidenceColor = !fc ? '' : {
    High:   'text-green dark:text-green-300 bg-green-light dark:bg-green-500/15 border-green-border dark:border-green-500/30',
    Medium: 'text-amber dark:text-amber-300 bg-amber-light dark:bg-amber-500/15 border-amber-border dark:border-amber-500/30',
    Low:    'text-text-muted bg-gray-100 dark:bg-white/10 border-border',
  }[fc.confidence]

  return (
    <div className="p-8 max-w-[1440px] mx-auto animate-fade-in space-y-8">
      <div className="page-header">
        <h1>Analysis</h1>
        <p>Risk scoring and underwriting notes</p>
      </div>

      {risk && cfg ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Risk score card */}
          <div className={clsx('lg:col-span-2 bg-white border rounded-2xl p-6 shadow-xs', cfg.border)}>
            <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted mb-5">Risk Assessment</p>
            <div className={clsx('w-14 h-14 rounded-2xl flex items-center justify-center mb-4', cfg.bg)}>
              <Icon size={24} className={cfg.text} strokeWidth={1.8} />
            </div>
            <div className="flex items-end gap-3 mb-4">
              <p className="font-mono text-[40px] font-semibold tracking-tight text-text-primary leading-none">
                {Number(risk.score).toFixed(0)}
              </p>
              <div className="mb-1">
                <p className="text-xs text-text-muted font-medium">risk score</p>
                <span className={clsx('badge', {
                  'badge-green': risk.level === 'Low Risk',
                  'badge-amber': risk.level === 'Medium Risk',
                  'badge-red':   risk.level === 'High Risk',
                })}>{risk.level}</span>
              </div>
            </div>
            <div className="h-2 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
              <div
                className={clsx('h-2 rounded-full transition-all duration-700', cfg.bar)}
                style={{ width: `${Math.min(100, risk.score)}%` }}
              />
            </div>
            <p className="text-[10px] text-text-muted mt-1.5">0 — 100 · lower is better</p>
          </div>

          {/* Underwriting notes */}
          <div className="lg:col-span-3 bg-card border border-border rounded-2xl p-6 shadow-xs">
            <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted mb-5">Underwriting Notes</p>
            <ul className="space-y-3">
              {risk.notes.map((note, i) => (
                <li key={i} className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 dark:bg-blue-300 mt-[7px] flex-shrink-0" />
                  <p className="text-sm text-text-secondary leading-relaxed">{note}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-2xl p-20 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-white/5 flex items-center justify-center mx-auto mb-4">
            <Shield size={22} className="text-gray-400 dark:text-slate-500" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">No risk data yet</p>
          <p className="text-xs text-text-muted">Upload statements on the Dashboard to generate a risk assessment</p>
        </div>
      )}

      {statements?.length > 0 && fc && (
        <>
          <div className="h-px bg-border" />

          {/* Revenue Forecast card */}
          <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
            <div className="flex items-start justify-between gap-6">
              {/* Left: metric */}
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm font-bold text-text-primary">Revenue Forecast</p>
                  <InfoTooltip>
                    <p className="font-semibold text-slate-300 mb-2">Revenue Forecast</p>
                    <p className="text-slate-400 leading-relaxed mb-2">
                      Predicted next month revenue using linear trend regression across all uploaded statements.
                    </p>
                    <div className="space-y-1 border-t border-white/10 pt-2">
                      <p className="text-slate-400"><span className="text-green-400 font-semibold">High confidence</span> — 6+ months of data</p>
                      <p className="text-slate-400"><span className="text-amber-400 font-semibold">Medium confidence</span> — 3–5 months</p>
                      <p className="text-slate-400"><span className="text-slate-400 font-semibold">Low confidence</span> — 1–2 months</p>
                    </div>
                  </InfoTooltip>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ml-1 ${confidenceColor}`}>
                    {fc.confidence} confidence
                  </span>
                </div>
                <p className="text-xs text-text-muted mb-4">Projected revenue for {fc.nextMonthLabel} · based on {fc.n} statement{fc.n !== 1 ? 's' : ''}</p>

                <div className="flex items-end gap-4">
                  <p className="font-mono text-[38px] font-bold text-text-primary leading-none">
                    {$fmt(fc.predicted)}
                  </p>
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <TrendIcon size={16} className={trendColor} strokeWidth={2} />
                    <span className={`text-sm font-semibold ${trendColor}`}>
                      {fc.deltaPct >= 0 ? '+' : ''}{fc.deltaPct.toFixed(1)}%
                    </span>
                    <span className="text-xs text-text-muted">vs last month</span>
                  </div>
                </div>
              </div>

              {/* Right: sparkline */}
              <div className="w-64 flex-shrink-0">
                <ForecastSparkline
                  statements={statements}
                  predicted={fc.predicted}
                  nextMonthLabel={fc.nextMonthLabel}
                />
                <p className="text-[10px] text-text-muted text-center mt-1">
                  — history &nbsp;·&nbsp; - - forecast
                </p>
              </div>
            </div>
          </div>

          {/* Row 1: Revenue vs Debits + Cash Flow */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3 bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">Revenue vs Debits</p>
                <span className="text-[10px] text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-1 rounded-full">Monthly</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Credits, debits and lender activity per statement</p>
              <RevenueChart statements={statements} />
            </div>
            <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">Cash Flow Trend</p>
                <span className={`text-[10px] font-semibold px-2 py-1 rounded-full ${
                  (statements.reduce((a, s) => a + (s.cash_flow ?? 0), 0)) >= 0
                    ? 'bg-green-light dark:bg-green-500/15 text-green dark:text-green-300'
                    : 'bg-red-light   dark:bg-red-500/15   text-red   dark:text-red-300'
                }`}>
                  {(statements.reduce((a, s) => a + (s.cash_flow ?? 0), 0)) >= 0 ? 'Positive' : 'Negative'}
                </span>
              </div>
              <p className="text-xs text-text-muted mb-6">Net cash position per statement</p>
              <CashFlowChart statements={statements} />
            </div>
          </div>

          {/* Row 2: Daily Balance Trend + Financial Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-2 bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">Daily Balance Trend</p>
                <span className="text-[10px] text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-1 rounded-full">Monthly</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Average daily balance per statement period</p>
              <DailyBalanceTrendChart statements={statements} />
            </div>
            <div className="lg:col-span-3 bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">Financial Overview</p>
                <span className="text-[10px] text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-1 rounded-full">Monthly</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Net cash flow, lender credits and avg daily balance per statement</p>
              <FinancialOverviewChart statements={statements} />
            </div>
          </div>

          {/* Row 3: Risk Indicators */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">Withholding Rate</p>
                <span className="text-[10px] text-text-muted bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-300 border border-amber-200 dark:border-amber-500/30 px-2 py-1 rounded-full font-semibold">Risk</span>
              </div>
              <p className="text-xs text-text-muted mb-6">% of revenue consumed by lender repayments</p>
              <WithholdingRateChart statements={statements} />
            </div>
            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-bold text-text-primary">NSF Count</p>
                <span className="text-[10px] text-text-muted bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300 border border-red-200 dark:border-red-500/30 px-2 py-1 rounded-full font-semibold">Risk</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Non-sufficient fund events per statement period</p>
              <NSFCountChart statements={statements} />
            </div>
            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-text-primary">Debt Load</p>
                  <InfoTooltip>
                    <p className="font-semibold text-slate-300 mb-2">What is Debt Load?</p>
                    <p className="text-slate-400 leading-relaxed mb-3">
                      Shows what % of total outflows are lender repayments vs. normal business expenses (rent, payroll, suppliers).
                    </p>
                    <div className="space-y-1.5 border-t border-white/10 pt-2">
                      <p className="text-slate-400"><span className="text-green-400 font-semibold">&lt; 15%</span> — healthy, room for another advance</p>
                      <p className="text-slate-400"><span className="text-amber-400 font-semibold">15–30%</span> — manageable, scrutinize cash flow</p>
                      <p className="text-slate-400"><span className="text-red-400 font-semibold">&gt; 30%</span> — stacked positions likely, high default risk</p>
                    </div>
                  </InfoTooltip>
                </div>
                <span className="text-[10px] text-text-muted bg-purple-50 dark:bg-purple-500/10 text-purple-600 dark:text-purple-300 border border-purple-200 dark:border-purple-500/30 px-2 py-1 rounded-full font-semibold">Risk</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Lender vs organic share of total outflows</p>
              <DebtLoadDonutChart totals={totals} />
            </div>
          </div>

          {/* Row 4: Trend Intelligence */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-text-primary">MoM Revenue Change</p>
                  <InfoTooltip>
                    <p className="font-semibold text-slate-300 mb-2">Month-over-Month Revenue Change</p>
                    <p className="text-slate-400 leading-relaxed">
                      % change in total credits vs. the prior statement. Consecutive red bars signal a deteriorating business even if absolute revenue looks healthy.
                    </p>
                  </InfoTooltip>
                </div>
                <span className="text-[10px] text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-1 rounded-full">Monthly</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Revenue growth or decline vs prior statement</p>
              <MoMRevenueChart statements={statements} />
            </div>

            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-text-primary">Balance / Obligation</p>
                  <InfoTooltip>
                    <p className="font-semibold text-slate-300 mb-2">Balance-to-Obligation Ratio</p>
                    <p className="text-slate-400 leading-relaxed mb-3">
                      Avg daily balance ÷ monthly lender debits. Shows if the business has enough cash on hand to cover its debt payments.
                    </p>
                    <div className="space-y-1.5 border-t border-white/10 pt-2">
                      <p className="text-slate-400"><span className="text-green-400 font-semibold">&gt; 2×</span> — healthy buffer</p>
                      <p className="text-slate-400"><span className="text-amber-400 font-semibold">1–2×</span> — watch closely</p>
                      <p className="text-slate-400"><span className="text-red-400 font-semibold">&lt; 1×</span> — balance less than one month of repayments</p>
                    </div>
                  </InfoTooltip>
                </div>
                <span className="text-[10px] text-text-muted bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-300 border border-red-200 dark:border-red-500/30 px-2 py-1 rounded-full font-semibold">Risk</span>
              </div>
              <p className="text-xs text-text-muted mb-6">Avg daily balance relative to lender obligations</p>
              <BalanceObligationChart statements={statements} />
            </div>

            <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-bold text-text-primary">Lender In vs Out</p>
                  <InfoTooltip>
                    <p className="font-semibold text-slate-300 mb-2">Lender In vs Out</p>
                    <p className="text-slate-400 leading-relaxed mb-3">
                      Compares MCA advances received (credits) vs repayments made (debits) per month.
                    </p>
                    <div className="space-y-1.5 border-t border-white/10 pt-2">
                      <p className="text-slate-400"><span className="text-green-400 font-semibold">Credits &gt; Debits</span> — new advances coming in, potential stacking</p>
                      <p className="text-slate-400"><span className="text-purple-400 font-semibold">Debits &gt; Credits</span> — net repayment mode, healthy wind-down</p>
                    </div>
                  </InfoTooltip>
                </div>
                <span className="text-[10px] text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-1 rounded-full">Monthly</span>
              </div>
              <p className="text-xs text-text-muted mb-6">MCA advances received vs repayments made</p>
              <LenderInOutChart statements={statements} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
