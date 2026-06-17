import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, File, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import { uploadStatements } from '../services/api'
import useStore from '../store/useStore'
import Toast from './Toast'

const ACCEPT = {
  'application/pdf': ['.pdf'],
  'image/*': ['.png', '.jpg', '.jpeg'],
  'text/csv': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
}

const FILE_ICONS = { pdf: FileText, csv: File, xlsx: File, xls: File }
const FILE_COLORS = {
  pdf:     'text-red-500   bg-red-50   dark:bg-red-500/15   dark:text-red-300',
  csv:     'text-green     bg-green-light dark:bg-green-500/15 dark:text-green-300',
  xlsx:    'text-blue-600  bg-blue-50  dark:bg-blue-500/15  dark:text-blue-300',
  default: 'text-gray-500  bg-gray-100 dark:bg-white/10     dark:text-slate-300',
}

function FileCard({ file, onRemove }) {
  const ext = file.name.split('.').pop().toLowerCase()
  const Icon = FILE_ICONS[ext] ?? File
  const color = FILE_COLORS[ext] ?? FILE_COLORS.default
  const size = file.size < 1024 * 1024
    ? `${(file.size / 1024).toFixed(0)} KB`
    : `${(file.size / 1024 / 1024).toFixed(1)} MB`

  return (
    <div className="flex items-center gap-3 bg-card border border-border rounded-xl px-4 py-3 shadow-xs group animate-fade-in">
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', color)}>
        <Icon size={14} strokeWidth={2} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary truncate">{file.name}</p>
        <p className="text-xs text-text-muted">{size}</p>
      </div>
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 w-6 h-6 rounded-full bg-gray-100 dark:bg-white/10
                   hover:bg-red-100 dark:hover:bg-red-500/20 hover:text-red dark:hover:text-red-300
                   flex items-center justify-center transition-all"
      >
        <X size={12} />
      </button>
    </div>
  )
}

export default function UploadZone() {
  const [files, setFiles] = useState([])
  const { clientId, isUploading, uploadError, setUploading, setUploadError, setResults, setUploadedFiles } = useStore()
  const [success, setSuccess] = useState(false)
  const [toast, setToast] = useState(null) // { type, message }

  const onDrop = useCallback((accepted) => {
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...accepted.filter((f) => !names.has(f.name))]
    })
    setUploadError(null)
    setSuccess(false)
  }, [setUploadError])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, accept: ACCEPT, multiple: true })
  const remove = (i) => setFiles((prev) => prev.filter((_, idx) => idx !== i))

  const handleProcess = async () => {
    if (!files.length) return
    setUploadedFiles(files)
    setUploading(true)
    setUploadError(null)
    setSuccess(false)
    try {
      const data = await uploadStatements(files, clientId)
      setResults(data)
      setSuccess(true)
      setFiles([])

      // Show lender app notification result if a client ID was provided
      if (clientId) {
        if (data.lender_app_notified) {
          setToast({ type: 'success', message: `Client ${clientId} · status ${data.lender_app_status}` })
        } else {
          setToast({ type: 'error', message: data.lender_app_status ?? 'Could not reach lender app' })
        }
      }
    } catch (err) {
      setUploadError(err.response?.data?.detail ?? err.message ?? 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={clsx(
          'relative border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 overflow-hidden',
          isDragActive
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-500/10 scale-[1.01]'
            : 'border-blue-200 dark:border-blue-500/30 bg-card hover:border-blue-400 hover:bg-blue-50/50 dark:hover:bg-blue-500/5'
        )}
      >
        <input {...getInputProps()} />

        {/* Subtle grid background */}
        <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />

        <div className="relative px-8 py-10 text-center">
          <div className={clsx(
            'w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center transition-all duration-200',
            isDragActive
              ? 'bg-blue-100 dark:bg-blue-500/20 scale-110'
              : 'bg-blue-50  dark:bg-blue-500/10'
          )}>
            <Upload size={24} className={isDragActive ? 'text-blue-600 dark:text-blue-300' : 'text-blue-400 dark:text-blue-400'} strokeWidth={1.5} />
          </div>
          <p className="text-sm font-semibold text-text-primary mb-1">
            {isDragActive ? 'Release to upload' : 'Drop bank statements here'}
          </p>
          <p className="text-xs text-text-muted">
            or <span className="text-blue-600 dark:text-blue-300 font-medium">browse files</span> · PDF, PNG, JPG, CSV, XLSX
          </p>
        </div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f, i) => <FileCard key={`${f.name}-${i}`} file={f} onRemove={() => remove(i)} />)}

          {uploadError && (
            <div className="flex items-start gap-3 bg-red-light dark:bg-red-500/10 border border-red-border dark:border-red-500/30 rounded-xl px-4 py-3 animate-fade-in">
              <AlertCircle size={16} className="text-red dark:text-red-300 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red dark:text-red-300 font-medium">{uploadError}</p>
            </div>
          )}

          <button
            onClick={handleProcess}
            disabled={isUploading}
            className="btn-primary w-full py-3 text-[13px]"
          >
            {isUploading
              ? <><Loader2 size={15} className="animate-spin" /> Analysing {files.length} file{files.length !== 1 ? 's' : ''}…</>
              : `Analyse ${files.length} file${files.length !== 1 ? 's' : ''} →`}
          </button>
        </div>
      )}

      {success && !files.length && (
        <div className="flex items-center gap-3 bg-green-light dark:bg-green-500/10 border border-green-border dark:border-green-500/30 rounded-xl px-4 py-3 animate-fade-in">
          <CheckCircle2 size={16} className="text-green dark:text-green-300 flex-shrink-0" />
          <p className="text-sm text-green-700 dark:text-green-300 font-medium">Analysis complete — results loaded below</p>
        </div>
      )}

      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  )
}
