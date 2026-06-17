import React, { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import clsx from 'clsx'
import Sidebar from './components/Sidebar'
import ThemeToggle from './components/ThemeToggle'
import Dashboard   from './pages/Dashboard'
import Statements  from './pages/Statements'
import Lenders     from './pages/Lenders'
import Analysis    from './pages/Analysis'
import Export      from './pages/Export'
import useStore    from './store/useStore'

const PAGE_META = {
  '/dashboard':  { label: 'Dashboard',  sub: 'Upload and analyse bank statements' },
  '/statements': { label: 'Statements', sub: 'Per-statement metrics overview' },
  '/lenders':    { label: 'Lenders',    sub: 'MCA and lender detection' },
  '/analysis':   { label: 'Analysis',   sub: 'Risk scoring and transactions' },
  '/export':     { label: 'Export',     sub: 'Download your results' },
}

function TopBar() {
  const { pathname } = useLocation()
  const { clientId, setClientId } = useStore()
  const meta = PAGE_META[pathname] ?? {}

  return (
    <header className="sticky top-0 z-10 bg-white/80 dark:bg-[#0E1629]/80 backdrop-blur-sm
                       border-b border-border flex items-center justify-between px-8 py-3
                       transition-colors duration-200">
      <div>
        <p className="font-sans text-[13px] font-bold text-text-primary leading-none">{meta.label}</p>
        <p className="font-sans text-[11px] text-text-muted mt-0.5">{meta.sub}</p>
      </div>
      <div className="flex items-center gap-3">
        <input
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="Client ID (optional)"
          className="text-xs px-3 py-1.5 bg-gray-50 dark:bg-white/5 border border-border rounded-lg outline-none
                     text-text-primary placeholder-text-muted focus:bg-white dark:focus:bg-white/10
                     focus:border-blue-300 focus:ring-1 focus:ring-blue-200 transition-all w-44"
        />
        <ThemeToggle />
        <img src="/CapInfBack.png" alt="Capital Infusion" className="w-7 h-7 rounded-full object-cover" />
      </div>
    </header>
  )
}

function ScrollToTop({ mainRef }) {
  const { pathname } = useLocation()
  useEffect(() => { mainRef.current?.scrollTo({ top: 0 }) }, [pathname])
  return null
}

function Layout() {
  const mainRef            = useRef(null)
  const { pathname }       = useLocation()
  const previewFilename    = useStore((s) => s.previewFilename)
  const loadCustomKeywords = useStore((s) => s.loadCustomKeywords)
  const splitViewActive    = pathname === '/dashboard' && Boolean(previewFilename)

  useEffect(() => { loadCustomKeywords() }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main
          ref={mainRef}
          className={clsx('flex-1', splitViewActive ? 'overflow-hidden' : 'overflow-y-auto')}
        >
          <ScrollToTop mainRef={mainRef} />
          <Routes>
            <Route path="/"            element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard"   element={<Dashboard />} />
            <Route path="/statements"  element={<Statements />} />
            <Route path="/lenders"     element={<Lenders />} />
            <Route path="/analysis"    element={<Analysis />} />
            <Route path="/export"      element={<Export />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  )
}
