import axios from 'axios'

// VITE_API_BASE_URL is set in .env.production → https://capital-infusion-ocr-1.onrender.com
// In dev it is empty so the Vite proxy (/api → localhost:8000) handles requests.
const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const client = axios.create({ baseURL: `${BASE}/api` })

export async function uploadStatements(files, clientId = '') {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (clientId) form.append('client_id', clientId)
  const { data } = await client.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function exportCSV(statements) {
  const { data } = await client.post('/export/csv', { statements }, { responseType: 'blob' })
  _download(data, 'orbit_statements.csv', 'text/csv')
}

export async function exportTransactions(transactions) {
  const { data } = await client.post('/export/transactions', { transactions }, { responseType: 'blob' })
  _download(data, 'orbit_transactions.csv', 'text/csv')
}

export async function exportJSON(payload) {
  const { data } = await client.post('/export/json', payload, { responseType: 'blob' })
  _download(data, 'orbit_export.json', 'application/json')
}

export async function fetchLenderKeywords() {
  const { data } = await client.get('/lender-keywords')
  return data
}

export async function addLenderKeyword(name, type) {
  const { data } = await client.post('/lender-keywords', { name, type })
  return data
}

export async function removeLenderKeyword(name, type) {
  const { data } = await client.delete('/lender-keywords', { data: { name, type } })
  return data
}

function _download(blob, filename, type) {
  const url = URL.createObjectURL(new Blob([blob], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
