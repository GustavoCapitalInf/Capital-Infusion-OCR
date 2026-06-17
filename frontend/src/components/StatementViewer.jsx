import React from 'react'
import { X, Download, FileText, Image as ImageIcon } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store/useStore'

function isPdf(file) {
  const name = (file?.name ?? '').toLowerCase()
  return file?.type === 'application/pdf' || name.endsWith('.pdf')
}

function isImage(file) {
  const name = (file?.name ?? '').toLowerCase()
  return (file?.type ?? '').startsWith('image/') || /\.(png|jpe?g|gif|webp)$/i.test(name)
}

export default function StatementViewer({ filename, onClose }) {
  const uploadedFiles = useStore((s) => s.uploadedFiles)
  const entry = filename ? uploadedFiles[filename] : null
  const file = entry?.file
  const url = entry?.url

  const handleDownload = () => {
    if (!file || !url) return
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
  }

  if (!filename || !file || !url) {
    return (
      <div className="flex flex-col h-full">
        <ViewerHeader filename={filename ?? 'Statement'} onClose={onClose} />
        <div className="flex-1 flex items-center justify-center p-8 text-center">
          <div>
            <FileText size={32} className="mx-auto text-text-dim mb-3" strokeWidth={1.5} />
            <p className="text-sm font-semibold text-text-primary mb-1">Preview unavailable</p>
            <p className="text-xs text-text-muted max-w-xs">
              Re-upload this statement to view it — originals are kept in your browser for the current session only.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <ViewerHeader filename={filename} onClose={onClose} onDownload={handleDownload} />

      <div className="flex-1 min-h-0 overflow-auto bg-gray-100 dark:bg-[#0A1020]">
        {isPdf(file) && (
          <iframe
            title={filename}
            src={url}
            className="w-full h-full min-h-[480px] border-0 bg-white"
          />
        )}

        {isImage(file) && (
          <div className="flex items-start justify-center p-4 min-h-full">
            <img
              src={url}
              alt={filename}
              className="max-w-full h-auto rounded-lg shadow-md border border-border"
            />
          </div>
        )}

        {!isPdf(file) && !isImage(file) && (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center gap-4">
            <ImageIcon size={32} className="text-text-dim" strokeWidth={1.5} />
            <div>
              <p className="text-sm font-semibold text-text-primary mb-1">No inline preview</p>
              <p className="text-xs text-text-muted mb-4">
                CSV and spreadsheet files can be downloaded but are not previewed here.
              </p>
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl
                           bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
              >
                <Download size={14} />
                Download file
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ViewerHeader({ filename, onClose, onDownload }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-card flex-shrink-0">
      <div className="w-8 h-8 rounded-lg bg-red-50 dark:bg-red-500/15 flex items-center justify-center flex-shrink-0">
        <FileText size={14} className="text-red-500 dark:text-red-300" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted leading-none mb-0.5">
          Statement Preview
        </p>
        <p className="text-sm font-semibold text-text-primary truncate" title={filename}>
          {filename}
        </p>
      </div>
      {onDownload && (
        <button
          type="button"
          onClick={onDownload}
          title="Download"
          aria-label="Download statement"
          className={iconBtnClass}
        >
          <Download size={15} />
        </button>
      )}
      <button
        type="button"
        onClick={onClose}
        title="Close preview"
        aria-label="Close statement preview"
        className={clsx(iconBtnClass, 'hover:bg-red-50 dark:hover:bg-red-500/15 hover:text-red dark:hover:text-red-300')}
      >
        <X size={15} />
      </button>
    </div>
  )
}

const iconBtnClass =
  'w-8 h-8 rounded-lg flex items-center justify-center text-text-muted ' +
  'hover:bg-gray-100 dark:hover:bg-white/10 hover:text-text-primary transition-colors cursor-pointer'
