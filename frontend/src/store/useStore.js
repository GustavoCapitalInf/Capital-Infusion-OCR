import { create } from 'zustand'

const useStore = create((set, get) => ({
  // Upload state
  isUploading: false,
  uploadError: null,
  clientId: '',

  // Analysis results (populated after upload)
  sessionId: null,
  statements: [],
  totals: null,
  averages: null,
  lenders: [],
  flagged: [],
  risk: null,
  transactions: [],

  // UI state
  activeTab: 'dashboard',
  kpiExpanded: { overall: false, monthly: false },

  // Actions
  setClientId: (id) => set({ clientId: id }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  toggleKpi: (key) =>
    set((s) => ({ kpiExpanded: { ...s.kpiExpanded, [key]: !s.kpiExpanded[key] } })),

  setUploading: (v) => set({ isUploading: v }),
  setUploadError: (e) => set({ uploadError: e }),

  setResults: (data) =>
    set({
      sessionId:    data.session_id,
      statements:   data.statements  ?? [],
      totals:       data.totals      ?? null,
      averages:     data.averages    ?? null,
      lenders:      data.lenders     ?? [],
      flagged:      data.flagged     ?? [],
      risk:         data.risk        ?? null,
      transactions: data.transactions ?? [],
      uploadError:  null,
    }),

  clearResults: () =>
    set({
      sessionId: null, statements: [], totals: null, averages: null,
      lenders: [], flagged: [], risk: null, transactions: [],
    }),

  // ── Add a transaction manually as a lender debit or credit ──────────────
  addManualLender: (txn, lenderName, type) =>
    set((state) => {
      const amount = type === 'debit'
        ? Number(txn.Debit  ?? 0)
        : Number(txn.Credit ?? 0)

      if (!amount || !lenderName.trim()) return state

      // Add to lenders list (visible in Lenders tab)
      const newLenderRow = {
        lender:    lenderName.trim(),
        keyword:   'manual',
        amount,
        statement: txn.statement ?? '',
        manual:    true,
        type,
      }

      const n = Math.max(state.statements.length, 1)

      // Recalculate totals
      const prevTotals = state.totals ?? {}
      const prevLdrDeb  = Number(prevTotals.lender_debits  ?? 0)
      const prevLdrCrd  = Number(prevTotals.lender_credits ?? 0)
      const totalCred   = Number(prevTotals.credits ?? 0)

      const newLdrDeb  = prevLdrDeb  + (type === 'debit'  ? amount : 0)
      const newLdrCrd  = prevLdrCrd  + (type === 'credit' ? amount : 0)
      const newWHRate  = totalCred > 0 ? (newLdrDeb / totalCred) * 100 : 0

      const newTotals = {
        ...prevTotals,
        lender_debits:    Number(newLdrDeb.toFixed(2)),
        lender_credits:   Number(newLdrCrd.toFixed(2)),
        withholding_rate: Number(newWHRate.toFixed(4)),
      }

      const prevAvg    = state.averages ?? {}
      const newAverages = {
        ...prevAvg,
        lender_debits:    Number((newLdrDeb / n).toFixed(2)),
        lender_credits:   Number((newLdrCrd / n).toFixed(2)),
        withholding_rate: Number(newWHRate.toFixed(4)),
      }

      return {
        lenders:  [...state.lenders, newLenderRow],
        totals:   newTotals,
        averages: newAverages,
      }
    }),
}))

export default useStore
