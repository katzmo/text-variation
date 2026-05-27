export const API = 'http://localhost:8000/api'

export async function fetchWitnesses() {
  const r = await fetch(`${API}/witnesses`)
  if (!r.ok) throw new Error('Failed to fetch witnesses')
  return r.json()
}

export async function fetchSegments() {
  const r = await fetch(`${API}/segments`)
  if (!r.ok) throw new Error('Failed to fetch segments')
  return r.json()
}

export async function postCollate(segmentId, witnessIds) {
  const r = await fetch(`${API}/collate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segment_id: segmentId, witness_ids: witnessIds }),
  })
  if (!r.ok) throw new Error(`Collate failed: ${r.status}`)
  return r.json()
}

export async function postUploadFiles(files, companionCsv) {
  const formData = new FormData()
  files.forEach((f) => {
    const blob = new Blob([f.content], {
      type: f.type === 'xml' ? 'application/xml' : 'text/plain',
    })
    formData.append('files', blob, f.name)
  })
  if (companionCsv) {
    const blob = new Blob([companionCsv.content], { type: 'text/csv' })
    formData.append('companion_csv', blob, companionCsv.name)
  }
  const r = await fetch(`${API}/upload`, { method: 'POST', body: formData })
  if (!r.ok) throw new Error('Upload failed')
  return r.json()
}

export async function postConfirmUpload(witnesses, replace = true) {
  const r = await fetch(`${API}/upload/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ witnesses, replace }),
  })
  if (!r.ok) throw new Error('Confirm failed')
  return r.json()
}

export async function fetchAlignWitnesses() {
  const r = await fetch(`${API}/align/witnesses`)
  if (!r.ok) throw new Error('Failed')
  return r.json()
}

export async function postRunAlignment(anchorId, threshold, topK = 15) {
  const r = await fetch(`${API}/align/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ anchor_id: anchorId, threshold, top_k: topK }),
  })
  if (!r.ok) throw new Error('Alignment failed')
  return r.json()
}

export async function fetchInspectAlignment(witnessId, limit = 100, offset = 0) {
  const r = await fetch(`${API}/align/inspect/${witnessId}?limit=${limit}&offset=${offset}`)
  if (!r.ok) throw new Error('Inspect failed')
  return r.json()
}

export async function postSaveAlignment() {
  const r = await fetch(`${API}/align/save`, { method: 'POST' })
  if (!r.ok) throw new Error('Save failed')
  return r.json()
}

export async function fetchAlignMatrix(maxRows = 0) {
  const r = await fetch(`${API}/align/matrix?max_rows=${maxRows}`)
  if (!r.ok) throw new Error('Matrix fetch failed')
  return r.json()
}
