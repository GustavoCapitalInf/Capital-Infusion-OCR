import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

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

function _download(blob, filename, type) {
  const url = URL.createObjectURL(new Blob([blob], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
