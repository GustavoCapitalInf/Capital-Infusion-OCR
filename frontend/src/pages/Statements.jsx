import React, { useState } from 'react'
import useStore from '../store/useStore'
import DataTable from '../components/DataTable'
import AddLenderModal from '../components/AddLenderModal'
import { FileText, Plus } from 'lucide-react'

const $ = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

function Badge({ text, variant = 'gray' }) {
  const cls = {
    green: 'badge badge-green', red: 'badge badge-red',
    amber: 'badge badge-amber', blue: 'badge badge-blue', gray: 'badge badge-gray',
  }[variant]
  return <span className={cls}>{text}</span>
}

const summaryCols = [
  {
    key: 'filename', label: 'Statement',
    render: (v) => (
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-500/15 flex items-center justify-center flex-shrink-0">
          <FileText size={12} className="text-blue-600 dark:text-blue-300" />
        </div>
        <span className="font-medium text-text-primary text-sm truncate max-w-[180px]">{v}</span>
      </div>
    ),
  },
  {
    key: 'statement_date', label: 'Period',
    render: (v, row) => {
      if (row.period_start && row.period_end) {
        const fmt = (iso) => {
          const [y, m, d] = iso.split('-')
          const mon = new Date(+y, +m - 1, 1).toLocaleString('en-US', { month: 'short' })
          return `${mon} ${parseInt(d)}, '${y.slice(2)}`
        }
        return <span className="text-text-secondary">{fmt(row.period_start)} – {fmt(row.period_end)}</span>
      }
      return <span className="text-text-secondary">{v ? v.slice(0, 7) : '—'}</span>
    },
  },
  { key: 'credits',        label: 'Credits',  render: (v) => <span className="font-semibold text-green">{$(v)}</span> },
  { key: 'debits',         label: 'Debits',   render: (v) => <span className="font-semibold text-red">{$(v)}</span> },
  { key: 'cash_flow',      label: 'Cash Flow',render: (v) => <span className={`font-semibold ${Number(v) >= 0 ? 'text-green' : 'text-red'}`}>{Number(v) >= 0 ? '+' : ''}{$(v)}</span> },
  { key: 'lender_debits',  label: 'Lender Debits', render: (v) => <span className="text-amber font-medium">{$(v)}</span> },
  {
    key: 'withholding_rate', label: 'W/H Rate',
    render: (v) => {
      const n = Number(v ?? 0)
      return <Badge text={`${n.toFixed(1)}%`} variant={n > 15 ? 'red' : n > 8 ? 'amber' : 'green'} />
    },
  },
  { key: 'nsf_count', label: 'NSF', render: (v) => <Badge text={String(v)} variant={v > 2 ? 'red' : v > 0 ? 'amber' : 'green'} /> },
  { key: 'avg_daily_balance', label: 'Avg Balance', render: (v) => <span className="text-text-secondary">{$(v)}</span> },
  { key: 'loan_count', label: 'Loans', render: (v) => <span className="badge badge-gray">{v}</span> },
  { key: 'pos_count',  label: 'POS',   render: (v) => <span className="badge badge-gray">{v}</span> },
]

export default function Statements() {
  const { statements, transactions } = useStore()
  const [modalTxn, setModalTxn] = useState(null)

  // Build transaction columns — inject the + action column
  const txnCols = [
    { key: 'Date',        label: 'Date',        render: (v) => <span className="font-mono text-xs text-text-secondary">{v || '—'}</span> },
    { key: 'Description', label: 'Description', render: (v) => <span className="text-text-primary font-medium text-sm truncate max-w-[240px] block">{v || '—'}</span> },
    { key: 'Credit',      label: 'Credit',      render: (v) => Number(v) > 0 ? <span className="font-semibold text-green text-sm">{$(v)}</span> : <span className="text-text-dim text-sm">—</span> },
    { key: 'Debit',       label: 'Debit',       render: (v) => Number(v) > 0 ? <span className="font-semibold text-red text-sm">{$(v)}</span>   : <span className="text-text-dim text-sm">—</span> },
    { key: 'Balance',     label: 'Balance',     render: (v) => v ? <span className="text-text-secondary text-sm">{$(v)}</span> : <span className="text-text-dim text-sm">—</span> },
    { key: 'statement',   label: 'File',        render: (v) => <span className="font-mono text-[11px] text-text-muted truncate max-w-[130px] block">{v}</span> },
    {
      // Action column — "+" button to add as lender
      key: '_add', label: '',
      render: (_, row) => (
        <button
          onClick={() => setModalTxn(row)}
          title="Add as lender"
          aria-label="Add transaction as lender"
          className="w-6 h-6 rounded-full flex items-center justify-center
                     bg-gray-100 dark:bg-white/10 text-text-muted border border-border
                     hover:bg-blue-50 dark:hover:bg-blue-500/15
                     hover:text-blue-600 dark:hover:text-blue-300
                     hover:border-blue-200 dark:hover:border-blue-500/40
                     transition-all duration-150 cursor-pointer"
        >
          <Plus size={11} strokeWidth={2.5} />
        </button>
      ),
    },
  ]

  if (statements.length === 0) return (
    <div className="p-8 max-w-[1440px] mx-auto animate-fade-in">
      <div className="page-header"><h1>Statements</h1><p>Per-statement breakdown of all uploaded bank statements</p></div>
      <div className="bg-card border border-border rounded-2xl p-20 text-center shadow-xs">
        <div className="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-white/5 flex items-center justify-center mx-auto mb-4">
          <FileText size={22} className="text-gray-400 dark:text-slate-500" strokeWidth={1.5} />
        </div>
        <p className="text-sm font-semibold text-text-primary mb-1">No statements yet</p>
        <p className="text-xs text-text-muted">Upload files on the Dashboard to get started</p>
      </div>
    </div>
  )

  return (
    <div className="p-8 max-w-[1440px] mx-auto animate-fade-in space-y-6">
      <div className="page-header">
        <h1>Statements</h1>
        <p>Per-statement breakdown and full transaction details</p>
      </div>

      <DataTable
        columns={summaryCols}
        data={statements}
        pageSize={25}
        title="Statement Summary"
        sub={`${statements.length} statement${statements.length !== 1 ? 's' : ''} processed`}
      />

      {transactions.length > 0 && (
        <DataTable
          columns={txnCols}
          data={transactions}
          pageSize={30}
          title="Transaction Details"
          sub={`${transactions.length.toLocaleString()} transactions · click + to add a row as a lender`}
          tabs={[
            { key: 'all',     label: 'All',     filter: () => true },
            { key: 'credits', label: 'Credits', filter: (r) => Number(r.Credit ?? 0) > 0 },
            { key: 'debits',  label: 'Debits',  filter: (r) => Number(r.Debit  ?? 0) > 0 },
          ]}
        />
      )}

      {/* Add-lender modal */}
      {modalTxn && (
        <AddLenderModal
          txn={modalTxn}
          onClose={() => setModalTxn(null)}
        />
      )}
    </div>
  )
}
