import React, { useMemo } from 'react'
import useStore from '../store/useStore'
import DataTable from '../components/DataTable'
import { Building2, AlertTriangle, Trash2, BookMarked, X } from 'lucide-react'

const $ = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

function StatCard({ label, value, sub, valueClass = 'text-text-primary' }) {
  return (
    <div className="bg-card border border-border rounded-2xl p-5 shadow-xs">
      <p className="text-[11px] font-bold uppercase tracking-[0.5px] text-text-muted mb-3">{label}</p>
      <p className={`text-[28px] font-extrabold tracking-tight leading-none ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-text-muted mt-1.5 font-medium">{sub}</p>}
    </div>
  )
}

const flaggedCols = [
  { key: 'keyword',   label: 'Keyword',  render: (v) => <span className="badge badge-red">{v}</span> },
  { key: 'amount',    label: 'Amount',   render: (v) => $(v) },
  { key: 'statement', label: 'Statement',render: (v) => <span className="text-xs text-text-muted">{v}</span> },
  { key: 'line',      label: 'Matched Line', render: (v) => <span className="text-xs text-text-secondary font-mono truncate max-w-xs block">{v}</span> },
]

export default function Lenders() {
  const { lenders, flagged, totals, removeManualLender, customLenderKeywords, removeCustomKeyword } = useStore()

  // Defined inside the component so it closes over removeManualLender
  const lenderCols = [
    {
      key: 'lender', label: 'Lender',
      render: (v, row) => (
        <div className="flex items-center gap-2">
          <span className="font-semibold text-text-primary">{v || 'Unknown'}</span>
          {row.keyword === 'saved'  && <span className="badge badge-blue">Saved</span>}
          {row.keyword === 'manual' && <span className="badge badge-gray">Manual</span>}
        </div>
      ),
    },
    {
      key: 'keyword', label: 'Type',
      render: (v, row) => (
        <span className={`badge ${row.type === 'credit' ? 'badge-green' : 'badge-amber'}`}>
          {row.type === 'credit' ? 'Credit' : 'Debit'}
        </span>
      ),
    },
    { key: 'amount',    label: 'Amount',   render: (v, row) => <span className={`font-bold ${row.type === 'credit' ? 'text-green' : 'text-amber'}`}>{$(v)}</span> },
    { key: 'statement', label: 'Statement',render: (v) => <span className="text-xs text-text-muted font-mono truncate max-w-[160px] block">{v}</span> },
    {
      key: '_remove', label: '',
      render: (_, row) => row.manual ? (
        <button
          onClick={() => removeManualLender(row.id)}
          title="Remove lender"
          aria-label="Remove manually added lender"
          className="w-6 h-6 rounded-full flex items-center justify-center
                     text-text-dim hover:bg-red-light dark:hover:bg-red-500/15
                     hover:text-red dark:hover:text-red-300 border border-transparent
                     hover:border-red-border dark:hover:border-red-500/30
                     transition-all duration-150 cursor-pointer"
        >
          <Trash2 size={11} strokeWidth={2} />
        </button>
      ) : null,
    },
  ]

  const totalsPerLender = useMemo(() => {
    const map = {}
    const seen = new Set()
    lenders.forEach(({ lender, amount, statement, monthly_amount }) => {
      const key = `${lender}::${statement ?? ''}`
      if (monthly_amount != null && monthly_amount > 0) {
        if (!seen.has(key)) {
          seen.add(key)
          map[lender] = (map[lender] ?? 0) + monthly_amount
        }
      } else {
        map[lender] = (map[lender] ?? 0) + amount
      }
    })
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Total Lender Debits"
            value={$(totals.lender_debits)}
            sub="Monthly est. (weekly × 4.33)"
            valueClass="text-amber dark:text-amber-400"
          />
          <StatCard
            label="Total Lender Credits"
            value={$(totals.lender_credits ?? 0)}
            sub="MCA advances received"
            valueClass="text-purple dark:text-purple-400"
          />
          <StatCard
            label="Withholding Rate"
            value={`${Number(totals.withholding_rate).toFixed(1)}%`}
            sub="Lender debits / total revenue"
            valueClass={totals.withholding_rate > 15 ? 'text-red dark:text-red-400' : totals.withholding_rate > 8 ? 'text-amber dark:text-amber-400' : 'text-green dark:text-green-400'}
          />
          <StatCard
            label="Unique Lenders"
            value={String(totalsPerLender.length)}
            sub="Distinct lenders identified"
          />
        </div>
      )}

      {/* Saved lender keywords */}
      <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
        <div className="flex items-center gap-2 mb-1">
          <BookMarked size={15} className="text-blue-600 dark:text-blue-300" />
          <p className="text-sm font-bold text-text-primary">Tracked Lender Keywords</p>
        </div>
        <p className="text-xs text-text-muted mb-4">
          Auto-applied to every future upload. Add new ones by clicking + on any transaction in the Statements tab.
        </p>
        {customLenderKeywords.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {customLenderKeywords.map((k, i) => (
              <div key={i} className="flex items-center gap-2 bg-gray-50 dark:bg-white/5 border border-border rounded-xl px-3 py-2">
                <span className={`badge ${k.type === 'credit' ? 'badge-green' : 'badge-amber'}`}>{k.type}</span>
                <span className="text-sm font-medium text-text-primary">{k.name}</span>
                <button
                  onClick={() => removeCustomKeyword(k.name, k.type)}
                  title="Remove keyword"
                  className="w-5 h-5 rounded-full flex items-center justify-center
                             text-text-dim hover:bg-red-light dark:hover:bg-red-500/15
                             hover:text-red dark:hover:text-red-300 border border-transparent
                             hover:border-red-border dark:hover:border-red-500/30
                             transition-all duration-150 ml-1 cursor-pointer"
                >
                  <X size={10} strokeWidth={2.5} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-text-muted italic">No saved keywords yet — add a lender from the Statements tab to get started.</p>
        )}
      </div>

      {/* Bar breakdown */}
      {totalsPerLender.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-6 shadow-xs">
          <p className="text-sm font-bold text-text-primary mb-1">Lender Breakdown</p>
          <p className="text-xs text-text-muted mb-6">Monthly obligation per lender (weekly payment × 4.33)</p>
          <div className="space-y-4">
            {totalsPerLender.map(({ lender, total }) => (
              <div key={lender} className="flex items-center gap-4">
                <div className="w-7 h-7 rounded-lg bg-amber-light dark:bg-amber-500/15 flex items-center justify-center flex-shrink-0">
                  <Building2 size={12} className="text-amber dark:text-amber-300" />
                </div>
                <span className="text-sm font-medium text-text-primary w-44 truncate">{lender || 'Unknown'}</span>
                <div className="flex-1 h-2 bg-gray-100 dark:bg-white/10 rounded-full overflow-hidden">
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
            <AlertTriangle size={15} className="text-red dark:text-red-400" />
            <p className="text-sm font-bold text-text-primary">Flagged Transactions</p>
            <span className="badge badge-red ml-1">{flagged.length}</span>
          </div>
          <p className="text-xs text-text-muted mb-4">Matches payment processors or suspicious keywords — excluded from revenue</p>
          <DataTable columns={flaggedCols} data={flagged} pageSize={20} />
        </div>
      )}

      {lenders.length === 0 && flagged.length === 0 && (
        <div className="bg-card border border-border rounded-2xl p-20 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-white/5 flex items-center justify-center mx-auto mb-4">
            <Building2 size={22} className="text-gray-400 dark:text-slate-500" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">No lender activity detected</p>
          <p className="text-xs text-text-muted">Upload statements on the Dashboard to analyse lender activity</p>
        </div>
      )}
    </div>
  )
}
