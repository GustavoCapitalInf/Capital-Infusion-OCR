import React from 'react'
import useStore from '../store/useStore'
import { ShieldCheck, ShieldAlert, Shield } from 'lucide-react'
import clsx from 'clsx'

const RISK_CONFIG = {
  'Low Risk':    { icon: ShieldCheck, bg: 'bg-green-light', border: 'border-green-border', text: 'text-green', bar: 'bg-green' },
  'Medium Risk': { icon: Shield,      bg: 'bg-amber-light', border: 'border-amber-border', text: 'text-amber', bar: 'bg-amber' },
  'High Risk':   { icon: ShieldAlert, bg: 'bg-red-light',   border: 'border-red-border',   text: 'text-red',   bar: 'bg-red' },
}

export default function Analysis() {
  const { risk } = useStore()
  const cfg  = risk ? (RISK_CONFIG[risk.level] ?? RISK_CONFIG['Low Risk']) : null
  const Icon = cfg?.icon ?? Shield

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
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={clsx('h-2 rounded-full transition-all duration-700', cfg.bar)}
                style={{ width: `${Math.min(100, risk.score)}%` }}
              />
            </div>
            <p className="text-[10px] text-text-muted mt-1.5">0 — 100 · lower is better</p>
          </div>

          {/* Underwriting notes */}
          <div className="lg:col-span-3 bg-white border border-border rounded-2xl p-6 shadow-xs">
            <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted mb-5">Underwriting Notes</p>
            <ul className="space-y-3">
              {risk.notes.map((note, i) => (
                <li key={i} className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-[7px] flex-shrink-0" />
                  <p className="text-sm text-text-secondary leading-relaxed">{note}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-border rounded-2xl p-20 text-center shadow-xs">
          <div className="w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <Shield size={22} className="text-gray-400" strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">No risk data yet</p>
          <p className="text-xs text-text-muted">Upload statements on the Dashboard to generate a risk assessment</p>
        </div>
      )}
    </div>
  )
}
