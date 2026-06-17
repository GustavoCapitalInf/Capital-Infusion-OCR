import React from 'react'
import {
  DollarSign, TrendingUp, TrendingDown, Percent, Building2,
  Banknote, Landmark, AlertTriangle, CreditCard,
  ChevronDown, ChevronUp,
} from 'lucide-react'
import MetricCard from './MetricCard'
import useStore from '../store/useStore'

const $ = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const pct = (n) => `${Number(n ?? 0).toFixed(1)}%`

export default function KpiGrid({ data, sectionKey = 'overall', n = 1 }) {
  const { kpiExpanded, toggleKpi } = useStore()
  const expanded = kpiExpanded[sectionKey] ?? false
  if (!data) return null

  const cfPos   = (data.cash_flow ?? 0) >= 0
  const nsf     = data.nsf_count ?? 0
  const wh      = data.withholding_rate ?? 0
  const whClr   = wh > 15 ? 'red' : wh > 8 ? 'amber' : 'none'
  const nsfClr  = nsf > 2 ? 'red' : nsf > 0 ? 'amber' : 'green'
  const avg     = n > 1 ? `Avg ${$(data.credits / n)} / mo` : undefined

  return (
    <div className="space-y-3 animate-fade-in">
      {/* Primary 6 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <MetricCard label="Total Revenue"     value={$(data.credits)}          sub={avg ?? 'Inbound deposits'}   icon={DollarSign}  accent="blue" />
        <MetricCard label="Lender Credits"    value={$(data.lender_credits)}   sub="MCA advances received"       icon={Banknote}    accent="purple" />
        <MetricCard label="True Revenue"      value={$(data.true_revenue)}     sub="Revenue minus lender credits" icon={TrendingUp}  accent="green" />
        <MetricCard label="Total Debits"      value={$(data.debits)}           sub="Outbound payments"           icon={TrendingDown} accent="red" />
        <MetricCard label="Withholding Rate"  value={pct(wh)}                  sub="Lender debits / revenue"     icon={Percent}     accent={whClr === 'none' ? 'blue' : whClr} />
        <MetricCard label="Lender Debits"     value={$(data.lender_debits)}    sub="Weekly payment × 4.33"       icon={Building2}   accent="amber" />
      </div>

      {/* Toggle */}
      <div className="flex justify-end">
        <button
          onClick={() => toggleKpi(sectionKey)}
          className="flex items-center gap-1.5 text-[11px] font-semibold text-text-muted hover:text-blue-600
                     dark:hover:text-blue-300
                     bg-card border border-border rounded-full px-4 py-1.5 shadow-xs
                     transition-all hover:border-blue-300 dark:hover:border-blue-500/40 hover:shadow-blue
                     cursor-pointer"
        >
          {expanded
            ? <><ChevronUp size={11} /> Show less</>
            : <><ChevronDown size={11} /> More metrics</>}
        </button>
      </div>

      {/* Secondary 4 */}
      {expanded && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-slide-down">
          <MetricCard
            label="Net Cash Flow"
            value={(cfPos ? '+' : '') + $(data.cash_flow)}
            sub="Credits minus debits"
            icon={cfPos ? TrendingUp : TrendingDown}
            accent={cfPos ? 'green' : 'red'}
            badge={cfPos ? 'Positive' : 'Negative'}
          />
          <MetricCard label="Avg Daily Balance" value={$(data.avg_daily_balance)} sub="Across statement period"  icon={Landmark}      accent="blue" />
          <MetricCard label="NSF Count"         value={String(nsf)}               sub="Returned / bounced items" icon={AlertTriangle}  accent={nsfClr} />
          <MetricCard label="Loan Count"         value={String(Math.round(data.loan_count ?? 0))} sub="Loan transactions detected" icon={CreditCard}  accent="none" />
        </div>
      )}
    </div>
  )
}
