import React, { useState, useEffect, useRef } from 'react'
import { X, Building2, TrendingDown, TrendingUp, Plus } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store/useStore'

const $ = (n) => `$${Number(n ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

export default function AddLenderModal({ txn, onClose }) {
  const [name, setName]   = useState('')
  const [type, setType]   = useState('debit')  // 'debit' | 'credit'
  const inputRef = useRef(null)
  const addManualLender = useStore((s) => s.addManualLender)
  const totals = useStore((s) => s.totals)

  // Focus input when modal opens
  useEffect(() => { inputRef.current?.focus() }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const amount    = type === 'debit' ? Number(txn.Debit ?? 0) : Number(txn.Credit ?? 0)
  const totalCred = Number(totals?.credits ?? 0)
  const prevLdrDeb= Number(totals?.lender_debits ?? 0)
  const newLdrDeb = prevLdrDeb + (type === 'debit' ? amount : 0)
  const newWHRate = totalCred > 0 ? (newLdrDeb / totalCred) * 100 : 0
  const prevWHRate= Number(totals?.withholding_rate ?? 0)
  const whDelta   = newWHRate - prevWHRate

  const handleAdd = () => {
    if (!name.trim() || !amount) return
    addManualLender(txn, name, type)
    onClose()
  }

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.45)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Modal */}
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md animate-slide-up border border-border overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center">
              <Building2 size={15} className="text-blue-600" />
            </div>
            <p className="font-sans text-[14px] font-bold text-text-primary">Add as Lender</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-7 h-7 rounded-full flex items-center justify-center text-text-muted
                       hover:bg-gray-100 hover:text-text-primary transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Transaction preview */}
          <div className="bg-gray-50 border border-border rounded-xl px-4 py-3">
            <p className="font-sans text-[11px] font-bold uppercase tracking-wider text-text-muted mb-1">
              Transaction
            </p>
            <p className="font-sans text-sm font-semibold text-text-primary truncate">
              {txn.Description || '—'}
            </p>
            <div className="flex items-center gap-4 mt-1">
              <span className="font-mono text-xs text-text-muted">{txn.Date || '—'}</span>
              {txn.Debit  > 0 && <span className="font-mono text-xs font-semibold text-red">-{$(txn.Debit)}</span>}
              {txn.Credit > 0 && <span className="font-mono text-xs font-semibold text-green">+{$(txn.Credit)}</span>}
            </div>
          </div>

          {/* Debit / Credit toggle */}
          <div>
            <p className="font-sans text-[11px] font-bold uppercase tracking-wider text-text-muted mb-2">
              Type
            </p>
            <div className="grid grid-cols-2 gap-2">
              {[
                { value: 'debit',  label: 'Lender Debit',  icon: TrendingDown, color: 'red',  disabled: !txn.Debit  },
                { value: 'credit', label: 'Lender Credit', icon: TrendingUp,   color: 'green', disabled: !txn.Credit },
              ].map(({ value, label, icon: Icon, color, disabled }) => (
                <button
                  key={value}
                  onClick={() => !disabled && setType(value)}
                  disabled={disabled}
                  className={clsx(
                    'flex items-center gap-2.5 px-4 py-3 rounded-xl border text-left transition-all',
                    type === value && !disabled
                      ? color === 'red'
                        ? 'bg-red-light border-red-border text-red'
                        : 'bg-green-light border-green-border text-green'
                      : 'border-border text-text-muted hover:border-gray-300',
                    disabled && 'opacity-40 cursor-not-allowed'
                  )}
                >
                  <Icon size={14} strokeWidth={2} />
                  <div>
                    <p className="font-sans text-[12px] font-semibold leading-none">{label}</p>
                    {!disabled && (
                      <p className="font-mono text-[11px] mt-0.5 opacity-70">
                        {$(value === 'debit' ? txn.Debit : txn.Credit)}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Lender name */}
          <div>
            <label htmlFor="lender-name" className="font-sans text-[11px] font-bold uppercase tracking-wider text-text-muted block mb-2">
              Lender Name
            </label>
            <input
              id="lender-name"
              ref={inputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleAdd() }}
              placeholder="e.g. Kapitus, Fundworks, BlueVine…"
              className="w-full font-sans text-sm px-4 py-2.5 bg-gray-50 border border-border rounded-xl
                         outline-none text-text-primary placeholder-text-muted
                         focus:bg-white focus:border-blue-300 focus:ring-2 focus:ring-blue-100
                         transition-all"
            />
          </div>

          {/* Impact preview */}
          {name.trim() && amount > 0 && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 space-y-1.5 animate-fade-in">
              <p className="font-sans text-[11px] font-bold uppercase tracking-wider text-blue-400 mb-2">
                Impact Preview
              </p>
              <div className="flex justify-between">
                <span className="font-sans text-xs text-text-secondary">
                  {type === 'debit' ? 'Lender Debits' : 'Lender Credits'}
                </span>
                <span className="font-mono text-xs font-semibold text-text-primary">
                  + {$(amount)}
                </span>
              </div>
              {type === 'debit' && (
                <div className="flex justify-between">
                  <span className="font-sans text-xs text-text-secondary">Withholding Rate</span>
                  <span className={clsx('font-mono text-xs font-semibold', whDelta > 0 ? 'text-red' : 'text-green')}>
                    {prevWHRate.toFixed(1)}% → {newWHRate.toFixed(1)}%
                    <span className="text-[10px] ml-1 opacity-70">
                      ({whDelta >= 0 ? '+' : ''}{whDelta.toFixed(2)}%)
                    </span>
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-6 py-4 border-t border-border bg-gray-50">
          <button
            onClick={onClose}
            className="flex-1 font-sans text-sm font-semibold text-text-secondary bg-white border border-border
                       rounded-xl py-2.5 hover:bg-gray-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            disabled={!name.trim() || !amount}
            className="flex-1 flex items-center justify-center gap-2 font-sans text-sm font-semibold
                       text-white bg-blue-600 rounded-xl py-2.5 hover:bg-blue-700 transition-all
                       disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            <Plus size={14} />
            Add Lender
          </button>
        </div>
      </div>
    </div>
  )
}
