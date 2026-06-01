import React, { useMemo } from 'react'
import useStore from '../store/useStore'
import DataTable from '../components/DataTable'
import { Building2, AlertTriangle } from 'lucide-react'

const $ = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

function StatCard({ label, value, sub, valueClass = 'text-text-primary' }) {
  return (
    <div className="bg-white border border-border rounded-2xl p-5 shadow-xs">
      <p className="text-[11px] font-bold uppercase tracking-[0.5px] text-text-muted mb-3">{label}</p>
      <p className={`text-[28px] font-extrabold tracking-tight leading-none ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-text-muted mt-1.5 font-medium">{sub}</p>}
    </div>
  )
}

const lenderCols = [
  { key: 'lender',    label: 'Lender',   render: (v) => <span className="font-semibold text-text-primary">{v || 'Unknown'}</span> },
  { key: 'keyword',   label: 'Keyword',  render: (v) => <span className="badge badge-blue">{v}</span> },
  { key: 'amount',    label: 'Amount',   render: (v) => <span className="font-bold text-amber">{$(v)}</span> },
  { key: 'statement', label: 'Statement',render: (v) => <span className="text-xs text-text-muted font-mono truncate max-w-[160px] block">{v}</span> },
]

const flaggedCols = [
  { key: 'keyword',   label: 'Keyword',  render: (v) => <span className="badge badge-red">{v}</span> },
  { key: 'amount',    label: 'Amount',   render: (v) => $(v) },
  { key: 'statement', label: 'Statement',render: (v) => <span className="text-xs text-text-muted">{v}</span> },
  { key: 'line',      label: 'Matched Line', render: (v) => <span className="text-xs text-text-secondary font-mono truncate max-w-xs block">{v}</span> },
]

export default function Lenders() {
  const { lenders, flagged, totals } = useStore()

  const totalsPerLender = useMemo(() => {
    const map = {}
    lenders.forEach(({ lender, amount }) => { map[lender] = (map[lender] ?? 0) + amount })
    return Object.entries(map).map(([lender, total]) => ({ lender, total })).sort((a, b) => b.total - a.total)
  }, [lenders])

  const max = totalsPerLender[0]?.total ?? 1

  return (
    <div className="p-8 max-w-[1440px] mx-auto animate-fade-in space-y-8">
      <div className="page-header">
        <h1>Lenders</h1>
        <p>MCA and lender activity detected across all statements</p>
      </div>

      {/* Summary row */}
      {totals && (
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="Total Lender Debits"
            value={$(totals.lender_debits)}
            sub="MCA repayments detected"
            valueClass="text-amber"
          />
          <StatCard
            label="Withholding Rate"
            value={`${Number(totals.withholding_rate).toFixed(1)}%`}
            sub="Lender debits / total revenue"
            valueClass={totals.withholding_rate > 15 ? 'text-red' : totals.withholding_rate > 8 ? 'text-amber' : 'text-green'}
          />
          <StatCard
            label="Unique Lenders"
            value={String(totalsPerLender.length)}
            sub="Distinct lenders identified"
          />
        </div>
      )}

      {/* Bar breakdown */}
      {totalsPerLender.length > 0 && (
        <div className="bg-white border border-border rounded-2xl p-6 shadow-xs">
          <p className="text-sm font-bold text-text-primary mb-1">Lender Breakdown</p>
          <p className="text-xs text-text-muted mb-6">Total repayments per detected lender</p>
          <div className="space-y-4">
            {totalsPerLender.map(({ lender, total }) => (
              <div key={lender} className="flex items-center gap-4">
                <div className="w-7 h-7 rounded-lg bg-amber-light flex items-center justify-center flex-shrink-0">
                  <Building2 size={12} className="text-amber" />
                </div>
                <span className="text-sm font-medium text-text-primary w-44 truncate">{lender || 'Unknown'}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all duration-500"
                    style={{ width: `${(total / max) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-text-primary w-28 text-right">{$(total)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lender transactions */}
      {lenders.length > 0 && (
        <DataTable
          columns={lenderCols}
          data={lenders}
          pageSize={20}
          title="Lender Transactions"
          sub="Individual transactions matched to known lenders"
        />
      )}

      {/* Flagged */}
      {flagged.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={15} className="text-red" />
            <p className="text-sm font-bold text-text-primary">Flagged Transactions</p>
            <span className="badge badge-red ml-1">{flagged.length}</span>
          </div>
          <p className="text-xs text-text-muted mb-4">Matches payment processors or suspicious keywords — excluded from revenue</p>
          <DataTable columns={flaggedCols} data={flagged} pageSize={20} />
        </div>
      )}

      {lenders.length === 0 && flagged.length === 0 && (
        <div className="bg-white border border-border rounded-2xl p-20 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <Building2 size={22} className="text-gray-400" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">No lender activity detected</p>
          <p className="text-xs text-text-muted">Upload statements on the Dashboard to analyse lender activity</p>
        </div>
      )}
    </div>
  )
}
