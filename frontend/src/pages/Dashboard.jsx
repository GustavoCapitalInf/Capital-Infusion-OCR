import React from 'react'
import { Sparkles, FileText, File } from 'lucide-react'
import useStore from '../store/useStore'
import UploadZone from '../components/UploadZone'
import KpiGrid from '../components/KpiGrid'

const FILE_ICON  = { pdf: FileText }
const FILE_COLOR = {
  pdf:     'text-red-500   bg-red-50   dark:bg-red-500/15   dark:text-red-300',
  csv:     'text-green     bg-green-light dark:bg-green-500/15 dark:text-green-300',
  xlsx:    'text-blue-600  bg-blue-50  dark:bg-blue-500/15  dark:text-blue-300',
  default: 'text-gray-500  bg-gray-100 dark:bg-white/10     dark:text-slate-300',
}

function UploadedFiles({ statements }) {
  if (!statements?.length) return null
  return (
    <div className="bg-card border border-border rounded-2xl p-5 shadow-xs animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.5px] text-text-muted">
          Uploaded Files
        </p>
        <span className="text-[10px] font-semibold text-text-muted bg-gray-100 dark:bg-white/10 px-2 py-0.5 rounded-full">
          {statements.length} file{statements.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {statements.map((s, i) => {
          const ext   = (s.filename ?? '').split('.').pop().toLowerCase()
          const Icon  = FILE_ICON[ext] ?? File
          const color = FILE_COLOR[ext] ?? FILE_COLOR.default
          const date  = s.statement_date ? s.statement_date.slice(0, 7) : null
          return (
            <div
              key={i}
              className="flex items-center gap-2 bg-gray-50 dark:bg-white/[0.04] border border-border rounded-xl px-3 py-2 max-w-[260px]"
            >
              <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 ${color}`}>
                <Icon size={12} strokeWidth={2} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-text-primary truncate leading-tight" title={s.filename}>
                  {s.filename}
                </p>
                {date && (
                  <p className="text-[10px] text-text-muted leading-tight">{date}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SectionDivider({ label }) {
  return (
    <div className="flex items-center gap-4 my-8">
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <span className="text-[10px] font-bold uppercase tracking-[2px] text-text-muted
                       px-4 py-1.5 bg-card border border-border rounded-full shadow-xs">
        {label}
      </span>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  )
}

function SectionBlock({ dot = 'blue', title, sub, badge, children }) {
  const dotStyle = dot === 'blue'
    ? 'bg-blue-600 shadow-blue/30'
    : 'bg-purple-600 shadow-purple/30'
  const badgeStyle = dot === 'blue'
    ? 'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30'
    : 'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/30'

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="flex items-center gap-4 bg-card border border-border rounded-2xl px-5 py-4 shadow-xs">
        <div className={`w-2.5 h-2.5 rounded-full shadow-md flex-shrink-0 ${dotStyle}`} />
        <div className="flex-1">
          <p className="text-[15px] font-bold text-text-primary leading-none">{title}</p>
          <p className="text-[12px] text-text-muted mt-1">{sub}</p>
        </div>
        <span className={`text-[11px] font-semibold px-3 py-1 rounded-full border ${badgeStyle}`}>{badge}</span>
      </div>
      {children}
    </div>
  )
}

export default function Dashboard() {
  const { totals, averages, statements } = useStore()
  const n = statements.length || 1

  return (
    <div className="p-8 max-w-[1440px] mx-auto">

      {/* Hero */}
      <div className="relative bg-gradient-to-br from-[#080E1C] via-[#0F1B33] to-[#0B1628]
                      rounded-3xl p-10 mb-8 overflow-hidden border border-white/8">
        {/* Glow blobs */}
        <div className="absolute -top-24 -right-16 w-96 h-96 rounded-full
                        bg-blue-600/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-16 left-1/3 w-64 h-64 rounded-full
                        bg-purple-600/8 blur-3xl pointer-events-none" />
        {/* Dot grid */}
        <div className="absolute inset-0 bg-grid opacity-20 pointer-events-none" />

        <div className="relative z-10 flex items-start justify-between gap-8">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 font-mono text-[10px] font-bold tracking-[2px] uppercase
                            text-blue-400 bg-blue-600/10 border border-blue-500/20 px-3 py-1.5 rounded-full mb-5">
              <Sparkles size={10} aria-hidden="true" />
              Orbit Optix · Financial Intelligence
            </div>
            {/* Calistoga display heading — design system: fintech SaaS Boutique pairing */}
            <h1 className="font-display text-[36px] font-normal text-white leading-[1.1] tracking-tight mb-3">
              Bank Statement{' '}
              <span className="text-gradient">Analysis</span>
            </h1>
            <p className="font-sans text-[14px] text-slate-300 leading-relaxed max-w-md">
              Upload bank statements to extract financial metrics, detect lender activity, and generate instant risk assessments.
            </p>
          </div>

          {/* Stats pill row */}
          {totals && (
            <div className="hidden lg:flex flex-col gap-2 min-w-[180px]">
              {[
                { label: 'Total Revenue',   val: `$${(totals.credits / 1000).toFixed(0)}k` },
                { label: 'NSF Count',       val: String(totals.nsf_count) },
                { label: 'Statements',      val: String(statements.length) },
              ].map(({ label, val }) => (
                <div key={label} className="flex items-center justify-between gap-4
                                             bg-white/5 border border-white/8 rounded-xl px-4 py-2.5">
                  <span className="text-[11px] text-slate-400 font-medium">{label}</span>
                  <span className="text-[13px] font-bold text-white">{val}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Upload */}
      <div className="mb-4">
        <p className="text-[11px] font-bold uppercase tracking-[1.5px] text-text-muted mb-3">
          Upload statements
        </p>
        <UploadZone />
      </div>

      {/* Uploaded file list */}
      {statements?.length > 0 && (
        <div className="mb-8">
          <UploadedFiles statements={statements} />
        </div>
      )}

      {/* Results */}
      {totals && (
        <div className="space-y-6 animate-fade-in">
          {/* Overall */}
          <SectionBlock
            dot="blue"
            title="Overall Totals"
            sub={`Cumulative across all ${n} statement${n !== 1 ? 's' : ''}`}
            badge="All time"
          >
            <KpiGrid data={totals} sectionKey="overall" n={n} />
          </SectionBlock>

          <SectionDivider label="Per month" />

          {/* Monthly average */}
          <SectionBlock
            dot="purple"
            title="Average Monthly"
            sub={`Per-statement averages across ${n} month${n !== 1 ? 's' : ''}`}
            badge="Per month"
          >
            <KpiGrid data={averages} sectionKey="monthly" n={1} />
          </SectionBlock>

        </div>
      )}
    </div>
  )
}
