import React, { useState } from 'react'
import { FileSpreadsheet, FileJson, FileText, Loader2, Download, CheckCircle2 } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store/useStore'
import { exportCSV, exportTransactions, exportJSON } from '../services/api'

const EXPORTS = [
  {
    id: 'statements',
    icon: FileSpreadsheet,
    title: 'Statement Summary',
    sub: 'Per-statement metrics — credits, debits, withholding rate, NSF, and more',
    format: 'CSV',
    accent: 'blue',
  },
  {
    id: 'transactions',
    icon: FileText,
    title: 'Transaction Details',
    sub: 'All parsed individual transactions across every uploaded statement',
    format: 'CSV',
    accent: 'green',
  },
  {
    id: 'json',
    icon: FileJson,
    title: 'Full JSON Export',
    sub: 'Complete analysis including totals, lenders, risk, and raw data',
    format: 'JSON',
    accent: 'purple',
  },
]

const ACCENT = {
  blue:   { icon: 'bg-blue-50     dark:bg-blue-500/15   text-blue-600  dark:text-blue-300',  btn: 'bg-blue-600   hover:bg-blue-700',   ring: 'hover:border-blue-300   dark:hover:border-blue-500/40 hover:shadow-blue/20',  badge: 'bg-blue-50     dark:bg-blue-500/15  text-blue-600  dark:text-blue-300  border-blue-200  dark:border-blue-500/30' },
  green:  { icon: 'bg-green-light dark:bg-green-500/15  text-green     dark:text-green-300', btn: 'bg-green      hover:bg-green-700',  ring: 'hover:border-green-200  dark:hover:border-green-500/40 hover:shadow-green/10', badge: 'bg-green-light dark:bg-green-500/15 text-green     dark:text-green-300 border-green-border dark:border-green-500/30' },
  purple: { icon: 'bg-purple-light dark:bg-purple-500/15 text-purple   dark:text-purple-300', btn: 'bg-purple    hover:bg-purple-700', ring: 'hover:border-purple-200 dark:hover:border-purple-500/40 hover:shadow-purple/10', badge: 'bg-purple-light dark:bg-purple-500/15 text-purple   dark:text-purple-300 border-purple-border dark:border-purple-500/30' },
}

export default function Export() {
  const { statements, transactions, totals, averages, lenders, risk } = useStore()
  const [loading,  setLoading]  = useState(null)
  const [done,     setDone]     = useState(null)
  const hasData = statements.length > 0

  const handle = async (id) => {
    setLoading(id)
    setDone(null)
    try {
      if (id === 'statements')   await exportCSV(statements)
      if (id === 'transactions') await exportTransactions(transactions)
      if (id === 'json')         await exportJSON({ statements, totals, averages, lenders, risk })
      setDone(id)
    } catch (e) { console.error(e) }
    finally { setLoading(null) }
  }

  return (
    <div className="p-8 max-w-[1440px] mx-auto animate-fade-in">
      <div className="page-header">
        <h1>Export</h1>
        <p>Download your analysis in multiple formats</p>
      </div>

      {!hasData ? (
        <div className="bg-card border border-border rounded-2xl p-20 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-white/5 flex items-center justify-center mx-auto mb-4">
            <Download size={22} className="text-gray-400 dark:text-slate-500" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">Nothing to export yet</p>
          <p className="text-xs text-text-muted">Upload and analyse statements first</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-8">
            {EXPORTS.map(({ id, icon: Icon, title, sub, format, accent }) => {
              const a = ACCENT[accent]
              const isLoading = loading === id
              const isDone    = done === id
              return (
                <div
                  key={id}
                  className={clsx(
                    'bg-card border border-border rounded-2xl p-6 shadow-xs transition-all duration-200 hover:shadow-md hover:-translate-y-0.5',
                    a.ring
                  )}
                >
                  <div className="flex items-start justify-between mb-5">
                    <div className={clsx('w-12 h-12 rounded-2xl flex items-center justify-center', a.icon)}>
                      <Icon size={22} strokeWidth={1.5} />
                    </div>
                    <span className={clsx('badge', a.badge)}>
                      {format}
                    </span>
                  </div>

                  <p className="text-[14px] font-bold text-text-primary mb-1.5">{title}</p>
                  <p className="text-[12px] text-text-muted leading-relaxed mb-6">{sub}</p>

                  <button
                    onClick={() => handle(id)}
                    disabled={isLoading}
                    className={clsx(
                      'w-full flex items-center justify-center gap-2 text-white rounded-xl py-2.5 text-sm font-semibold transition-all shadow-xs hover:shadow-md disabled:opacity-60',
                      a.btn
                    )}
                  >
                    {isLoading
                      ? <><Loader2 size={14} className="animate-spin" /> Exporting…</>
                      : isDone
                      ? <><CheckCircle2 size={14} /> Downloaded</>
                      : <><Download size={14} /> Download {format}</>}
                  </button>
                </div>
              )
            })}
          </div>

          {/* Data summary */}
          <div className="bg-card border border-border rounded-2xl p-5 shadow-xs">
            <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted mb-4">Export Summary</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Statements',    val: statements.length },
                { label: 'Transactions',  val: transactions.length.toLocaleString() },
                { label: 'Lender Rows',   val: lenders.length },
                { label: 'Risk Level',    val: risk?.level ?? '—' },
              ].map(({ label, val }) => (
                <div key={label} className="text-center p-3 rounded-xl bg-gray-50 dark:bg-white/[0.03] border border-border">
                  <p className="text-[20px] font-extrabold text-text-primary tracking-tight">{val}</p>
                  <p className="text-[11px] text-text-muted font-medium mt-0.5">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
