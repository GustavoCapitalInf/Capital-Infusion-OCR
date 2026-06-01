import { create } from 'zustand'

const useStore = create((set) => ({
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
}))

export default useStore
