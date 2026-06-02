import React, { useMemo, useState } from 'react'
import { Search, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import clsx from 'clsx'

export default function DataTable({ columns, data, pageSize = 20, title, sub }) {
  const [query,  setQuery]  = useState('')
  const [page,   setPage]   = useState(1)
  const [sort,   setSort]   = useState(null)

  const filtered = useMemo(() => {
    if (!query.trim()) return data
    const q = query.toLowerCase()
    return data.filter((row) =>
      Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(q))
    )
  }, [data, query])

  const sorted = useMemo(() => {
    if (!sort) return filtered
    return [...filtered].sort((a, b) => {
      const av = a[sort.key] ?? '', bv = b[sort.key] ?? ''
      const cmp = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv))
      return sort.dir === 'asc' ? cmp : -cmp
    })
  }, [filtered, sort])

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize))
  const rows       = sorted.slice((page - 1) * pageSize, page * pageSize)

  const toggleSort = (key) => {
    setPage(1)
    setSort((prev) =>
      prev?.key === key
        ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' }
    )
  }

  const SortIcon = ({ colKey }) => {
    if (sort?.key !== colKey) return <ChevronsUpDown size={10} className="opacity-30" />
    return sort.dir === 'asc'
      ? <ChevronUp size={10} className="text-blue-600 dark:text-blue-300" />
      : <ChevronDown size={10} className="text-blue-600 dark:text-blue-300" />
  }

  return (
    <div className="bg-card border border-border rounded-2xl shadow-xs overflow-hidden">
      {/* Table header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-border-light">
        <div>
          {title && <p className="text-sm font-bold text-text-primary">{title}</p>}
          {sub && <p className="text-xs text-text-muted mt-0.5">{sub}</p>}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted bg-gray-100 dark:bg-white/10 px-2.5 py-1 rounded-full font-medium">
            {sorted.length.toLocaleString()} rows
          </span>
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
            <input
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(1) }}
              placeholder="Search…"
              className="pl-8 pr-3 py-1.5 text-xs bg-gray-50 dark:bg-white/5 border border-border rounded-lg outline-none
                         text-text-primary placeholder-text-muted focus:bg-white dark:focus:bg-white/10 focus:border-blue-300
                         focus:ring-1 focus:ring-blue-200 transition-all w-48"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-light">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  className="px-5 py-3 text-left bg-gray-50/80 dark:bg-white/[0.03] cursor-pointer select-none group"
                >
                  <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-text-muted group-hover:text-text-secondary transition-colors whitespace-nowrap">
                    {col.label}
                    <SortIcon colKey={col.key} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border-light">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-5 py-16 text-center">
                  <p className="text-sm text-text-muted">No results found</p>
                  {query && <p className="text-xs text-text-dim mt-1">Try a different search term</p>}
                </td>
              </tr>
            ) : rows.map((row, i) => (
              <tr
                key={i}
                className={clsx(
                  'transition-colors hover:bg-gray-50/80 dark:hover:bg-white/[0.04]',
                  i % 2 === 1 && 'bg-gray-50/30 dark:bg-white/[0.02]'
                )}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-5 py-3 text-text-secondary whitespace-nowrap">
                    {col.render ? col.render(row[col.key], row) : (
                      <span className="text-sm">{String(row[col.key] ?? '—')}</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-3 border-t border-border-light bg-gray-50/50 dark:bg-white/[0.02]">
          <p className="text-xs text-text-muted">
            Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, sorted.length)} of {sorted.length}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)} disabled={page === 1}
              className="px-2 py-1 text-xs text-text-secondary rounded-lg border border-border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >«</button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1 text-xs text-text-secondary rounded-lg border border-border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >Prev</button>
            <span className="px-3 py-1 text-xs font-semibold text-blue-600 bg-blue-50 border border-blue-200
                              dark:text-blue-300 dark:bg-blue-500/15 dark:border-blue-500/30 rounded-lg">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-3 py-1 text-xs text-text-secondary rounded-lg border border-border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >Next</button>
            <button
              onClick={() => setPage(totalPages)} disabled={page === totalPages}
              className="px-2 py-1 text-xs text-text-secondary rounded-lg border border-border disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >»</button>
          </div>
        </div>
      )}
    </div>
  )
}
