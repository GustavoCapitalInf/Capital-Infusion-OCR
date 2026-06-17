import { create } from 'zustand'
import { fetchLenderKeywords, addLenderKeyword, removeLenderKeyword } from '../services/api'

// Apply saved keywords to fresh upload data, augmenting lenders + totals
function applyCustomKeywords(data, keywords) {
  if (!keywords.length || !data.transactions?.length) return data

  const autoLenders = []
  let extraLdrDeb = 0
  let extraLdrCrd = 0

  keywords.forEach(({ name, type }) => {
    const kw = name.toLowerCase()
    data.transactions
      .filter((t) =>
        (t.Description ?? '').toLowerCase().includes(kw) &&
        (type === 'debit' ? Number(t.Debit ?? 0) > 0 : Number(t.Credit ?? 0) > 0)
      )
      .forEach((txn, i) => {
        const amount = type === 'debit' ? Number(txn.Debit ?? 0) : Number(txn.Credit ?? 0)
        if (amount > 0) {
          autoLenders.push({
            id:        `saved_${Date.now()}_${autoLenders.length}_${i}`,
            lender:    name,
            keyword:   'saved',
            amount,
            statement: txn.statement ?? '',
            manual:    true,
            type,
          })
          if (type === 'debit') extraLdrDeb += amount
          else extraLdrCrd += amount
        }
      })
  })

  if (!autoLenders.length) return data

  const n          = Math.max((data.statements ?? []).length, 1)
  const baseTotals = data.totals ?? {}
  const newLdrDeb  = Number(baseTotals.lender_debits  ?? 0) + extraLdrDeb
  const newLdrCrd  = Number(baseTotals.lender_credits ?? 0) + extraLdrCrd
  const totalCred  = Number(baseTotals.credits ?? 0)
  const newTrueRev = totalCred - newLdrCrd
  const newWHRate  = newTrueRev > 0 ? (newLdrDeb / newTrueRev) * 100 : 0

  return {
    ...data,
    lenders:  [...(data.lenders ?? []), ...autoLenders],
    totals:   {
      ...baseTotals,
      lender_debits:    Number(newLdrDeb.toFixed(2)),
      lender_credits:   Number(newLdrCrd.toFixed(2)),
      withholding_rate: Number(newWHRate.toFixed(4)),
    },
    averages: {
      ...(data.averages ?? {}),
      lender_debits:    Number((newLdrDeb / n).toFixed(2)),
      lender_credits:   Number((newLdrCrd / n).toFixed(2)),
      withholding_rate: Number(newWHRate.toFixed(4)),
    },
  }
}

// ─────────────────────────────────────────────────────────────────────────────

// ── Theme bootstrap (runs once on module load — before React paints) ─────────
function readInitialTheme() {
  if (typeof window === 'undefined') return 'light'
  try {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark' || saved === 'light') return saved
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function applyThemeToDOM(theme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (theme === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

const initialTheme = readInitialTheme()
applyThemeToDOM(initialTheme)

function revokeUploadedFiles(filesMap) {
  Object.values(filesMap ?? {}).forEach(({ url }) => {
    if (url) URL.revokeObjectURL(url)
  })
}

const useStore = create((set, get) => ({
  // Theme
  theme: initialTheme,
  setTheme: (theme) => {
    applyThemeToDOM(theme)
    try { localStorage.setItem('theme', theme) } catch {}
    set({ theme })
  },
  toggleTheme: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark'
    applyThemeToDOM(next)
    try { localStorage.setItem('theme', next) } catch {}
    set({ theme: next })
  },

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

  // Original uploaded files for in-app preview (session-only, browser memory)
  uploadedFiles: {},
  previewFilename: null,
  previewPanelWidth: 42,

  // Persisted custom lender keywords (populated from server on app load)
  customLenderKeywords: [],

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

  setUploadedFiles: (files) => {
    const prev = get().uploadedFiles
    revokeUploadedFiles(prev)
    const uploadedFiles = {}
    files.forEach((f) => {
      uploadedFiles[f.name] = { file: f, url: URL.createObjectURL(f) }
    })
    const prevPreview = get().previewFilename
    const stillExists = prevPreview && uploadedFiles[prevPreview]
    set({
      uploadedFiles,
      previewFilename: stillExists ? prevPreview : null,
    })
  },

  openStatementPreview: (filename) => set({ previewFilename: filename }),
  closeStatementPreview: () => set({ previewFilename: null }),
  setPreviewPanelWidth: (width) =>
    set({ previewPanelWidth: Math.min(85, Math.max(15, width)) }),

  setResults: (data) =>
    set((state) => {
      const augmented = applyCustomKeywords(data, state.customLenderKeywords)
      return {
        sessionId:    augmented.session_id,
        statements:   augmented.statements  ?? [],
        totals:       augmented.totals      ?? null,
        averages:     augmented.averages    ?? null,
        lenders:      augmented.lenders     ?? [],
        flagged:      augmented.flagged     ?? [],
        risk:         augmented.risk        ?? null,
        transactions: augmented.transactions ?? [],
        uploadError:  null,
      }
    }),

  clearResults: () => {
    revokeUploadedFiles(get().uploadedFiles)
    set({
      sessionId: null, statements: [], totals: null, averages: null,
      lenders: [], flagged: [], risk: null, transactions: [],
      uploadedFiles: {}, previewFilename: null,
    })
  },

  // ── Add ALL matching transactions for a lender + save keyword ────────────
  addManualLenderBulk: (txns, lenderName, type) =>
    set((state) => {
      if (!txns.length || !lenderName.trim()) return state

      const newRows = txns
        .map((txn, i) => ({
          id:        `manual_${Date.now()}_${i}`,
          lender:    lenderName.trim(),
          keyword:   'manual',
          amount:    type === 'debit' ? Number(txn.Debit ?? 0) : Number(txn.Credit ?? 0),
          statement: txn.statement ?? '',
          manual:    true,
          type,
        }))
        .filter((r) => r.amount > 0)

      const totalAmount = newRows.reduce((sum, r) => sum + r.amount, 0)
      if (!totalAmount) return state

      const n          = Math.max(state.statements.length, 1)
      const prevTotals = state.totals ?? {}
      const prevLdrDeb = Number(prevTotals.lender_debits  ?? 0)
      const prevLdrCrd = Number(prevTotals.lender_credits ?? 0)
      const totalCred  = Number(prevTotals.credits ?? 0)

      const newLdrDeb = prevLdrDeb + (type === 'debit'  ? totalAmount : 0)
      const newLdrCrd = prevLdrCrd + (type === 'credit' ? totalAmount : 0)
      const newTrueRev = totalCred - newLdrCrd
      const newWHRate = newTrueRev > 0 ? (newLdrDeb / newTrueRev) * 100 : 0

      // Persist keyword server-side (fire-and-forget; optimistic UI update)
      const alreadySaved = state.customLenderKeywords.some(
        (k) => k.name.toLowerCase() === lenderName.trim().toLowerCase() && k.type === type
      )
      const newKeywords = alreadySaved
        ? state.customLenderKeywords
        : [...state.customLenderKeywords, { name: lenderName.trim(), type }]

      if (!alreadySaved) {
        addLenderKeyword(lenderName.trim(), type)
          .then((updated) => set({ customLenderKeywords: updated }))
          .catch(console.error)
      }

      return {
        lenders: [...state.lenders, ...newRows],
        totals:  {
          ...prevTotals,
          lender_debits:    Number(newLdrDeb.toFixed(2)),
          lender_credits:   Number(newLdrCrd.toFixed(2)),
          true_revenue:     Number(newTrueRev.toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
        averages: {
          ...(state.averages ?? {}),
          lender_debits:    Number((newLdrDeb / n).toFixed(2)),
          lender_credits:   Number((newLdrCrd / n).toFixed(2)),
          true_revenue:     Number((newTrueRev / n).toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
        customLenderKeywords: newKeywords,
      }
    }),

  // ── Add a single transaction manually ────────────────────────────────────
  addManualLender: (txn, lenderName, type) =>
    set((state) => {
      const amount = type === 'debit'
        ? Number(txn.Debit  ?? 0)
        : Number(txn.Credit ?? 0)

      if (!amount || !lenderName.trim()) return state

      const newLenderRow = {
        id:        `manual_${Date.now()}`,
        lender:    lenderName.trim(),
        keyword:   'manual',
        amount,
        statement: txn.statement ?? '',
        manual:    true,
        type,
      }

      const n          = Math.max(state.statements.length, 1)
      const prevTotals = state.totals ?? {}
      const prevLdrDeb = Number(prevTotals.lender_debits  ?? 0)
      const prevLdrCrd = Number(prevTotals.lender_credits ?? 0)
      const totalCred  = Number(prevTotals.credits ?? 0)

      const newLdrDeb = prevLdrDeb + (type === 'debit'  ? amount : 0)
      const newLdrCrd = prevLdrCrd + (type === 'credit' ? amount : 0)
      const newTrueRev = totalCred - newLdrCrd
      const newWHRate = newTrueRev > 0 ? (newLdrDeb / newTrueRev) * 100 : 0

      return {
        lenders:  [...state.lenders, newLenderRow],
        totals:   {
          ...prevTotals,
          lender_debits:    Number(newLdrDeb.toFixed(2)),
          lender_credits:   Number(newLdrCrd.toFixed(2)),
          true_revenue:     Number(newTrueRev.toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
        averages: {
          ...(state.averages ?? {}),
          lender_debits:    Number((newLdrDeb / n).toFixed(2)),
          lender_credits:   Number((newLdrCrd / n).toFixed(2)),
          true_revenue:     Number((newTrueRev / n).toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
      }
    }),

  // ── Remove a manually added lender row ───────────────────────────────────
  removeManualLender: (id) =>
    set((state) => {
      const row = state.lenders.find((l) => l.id === id)
      if (!row) return state

      const n      = Math.max(state.statements.length, 1)
      const amount = Number(row.amount ?? 0)

      const prevTotals = state.totals  ?? {}
      const prevLdrDeb = Number(prevTotals.lender_debits  ?? 0)
      const prevLdrCrd = Number(prevTotals.lender_credits ?? 0)
      const totalCred  = Number(prevTotals.credits ?? 0)

      const newLdrDeb = Math.max(0, prevLdrDeb - (row.type === 'debit'  ? amount : 0))
      const newLdrCrd = Math.max(0, prevLdrCrd - (row.type === 'credit' ? amount : 0))
      const newTrueRev = totalCred - newLdrCrd
      const newWHRate = newTrueRev > 0 ? (newLdrDeb / newTrueRev) * 100 : 0

      return {
        lenders:  state.lenders.filter((l) => l.id !== id),
        totals:   {
          ...prevTotals,
          lender_debits:    Number(newLdrDeb.toFixed(2)),
          lender_credits:   Number(newLdrCrd.toFixed(2)),
          true_revenue:     Number(newTrueRev.toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
        averages: {
          ...(state.averages ?? {}),
          lender_debits:    Number((newLdrDeb / n).toFixed(2)),
          lender_credits:   Number((newLdrCrd / n).toFixed(2)),
          true_revenue:     Number((newTrueRev / n).toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        },
      }
    }),

  // ── Load keywords from server (called once on app start) ─────────────────
  loadCustomKeywords: async () => {
    try {
      const keywords = await fetchLenderKeywords()
      set({ customLenderKeywords: keywords })
    } catch (e) {
      console.error('Failed to load lender keywords', e)
    }
  },

  // ── Remove a saved keyword + all matching manual lender rows ─────────────
  removeCustomKeyword: (name, type) => {
    set((state) => {
      const nameLower = name.toLowerCase()

      // All manually-added rows that came from this keyword (saved or manual)
      const toRemove = state.lenders.filter(
        (l) => l.manual === true &&
               (l.lender ?? '').toLowerCase() === nameLower &&
               l.type === type
      )

      const removedAmount = toRemove.reduce((sum, l) => sum + Number(l.amount ?? 0), 0)
      const removeIds     = new Set(toRemove.map((l) => l.id))

      const n          = Math.max(state.statements.length, 1)
      const prevTotals = state.totals ?? {}
      const prevLdrDeb = Number(prevTotals.lender_debits  ?? 0)
      const prevLdrCrd = Number(prevTotals.lender_credits ?? 0)
      const totalCred  = Number(prevTotals.credits ?? 0)

      const newLdrDeb = Math.max(0, prevLdrDeb - (type === 'debit'  ? removedAmount : 0))
      const newLdrCrd = Math.max(0, prevLdrCrd - (type === 'credit' ? removedAmount : 0))
      const newTrueRev = totalCred - newLdrCrd
      const newWHRate = newTrueRev > 0 ? (newLdrDeb / newTrueRev) * 100 : 0

      return {
        customLenderKeywords: state.customLenderKeywords.filter(
          (k) => !(k.name.toLowerCase() === nameLower && k.type === type)
        ),
        lenders: state.lenders.filter((l) => !removeIds.has(l.id)),
        totals: removedAmount > 0 ? {
          ...prevTotals,
          lender_debits:    Number(newLdrDeb.toFixed(2)),
          lender_credits:   Number(newLdrCrd.toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        } : prevTotals,
        averages: removedAmount > 0 ? {
          ...(state.averages ?? {}),
          lender_debits:    Number((newLdrDeb / n).toFixed(2)),
          lender_credits:   Number((newLdrCrd / n).toFixed(2)),
          withholding_rate: Number(newWHRate.toFixed(4)),
        } : state.averages,
      }
    })

    // Server-side keyword removal (fire-and-forget; confirm with server list)
    removeLenderKeyword(name, type)
      .then((updated) => set({ customLenderKeywords: updated }))
      .catch(console.error)
  },
}))

export default useStore
