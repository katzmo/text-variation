// ── Similarity ─────────────────────────────────────────────────────────────
export function jaccard(a, b) {
  const sa = new Set(a.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/))
  const sb = new Set(b.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/))
  let inter = 0
  for (const w of sa) if (sb.has(w)) inter++
  return inter / (sa.size + sb.size - inter || 1)
}

// ── UPGMA dendrogram ────────────────────────────────────────────────────────
export function upgma(ids, getTextFn) {
  const n = ids.length
  const NS = 8 // number of segments to sample for distance
  const dist = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => {
      if (i === j) return 0
      let s = 0
      for (let k = 0; k < NS; k++) s += jaccard(getTextFn(ids[i], k), getTextFn(ids[j], k))
      return 1 - s / NS
    })
  )

  let nodes = ids.map((id, i) => ({ id, i, left: null, right: null, h: 0, leaves: [i] }))
  let act = [...Array(n).keys()]
  const sz = new Array(n).fill(1)

  while (act.length > 1) {
    let md = Infinity, pi = -1, pj = -1
    for (let ii = 0; ii < act.length; ii++)
      for (let jj = ii + 1; jj < act.length; jj++)
        if (dist[act[ii]][act[jj]] < md) { md = dist[act[ii]][act[jj]]; pi = ii; pj = jj }

    const i = act[pi], j = act[pj]
    const m = {
      id: `[${nodes[i].id}+${nodes[j].id}]`, i: nodes.length,
      left: nodes[i], right: nodes[j], h: md / 2,
      leaves: [...nodes[i].leaves, ...nodes[j].leaves],
    }
    nodes.push(m)
    const ni = nodes.length - 1
    for (let k = 0; k <= ni; k++) { if (!dist[k]) dist[k] = []; dist[k][ni] = 0 }
    dist[ni] = new Array(ni + 1).fill(0)
    for (const k of act) {
      if (k === i || k === j) continue
      const d = (dist[i][k] * sz[i] + dist[j][k] * sz[j]) / (sz[i] + sz[j])
      dist[ni][k] = dist[k][ni] = d
    }
    sz.push(sz[i] + sz[j])
    act = act.filter(k => k !== i && k !== j).concat([ni])
  }
  return nodes[act[0]]
}

export function leafOrder(node) {
  if (!node.left && !node.right) return [node.id]
  return [...leafOrder(node.left), ...leafOrder(node.right)]
}

// ── Text normalization (for collation settings) ────────────────────────────
export function normalizeText(t, variation) {
  let s = t.toLowerCase()
  if (!variation.includes('punctuation')) s = s.replace(/[^\w\s]/g, '')
  if (!variation.includes('orthography') || !variation.includes('spelling')) {
    s = s.replace(/(.)\1+/g, '$1')
    s = s.replace(/our\b/g, 'or').replace(/ise\b/g, 'ize').replace(/eth\b/g, 's')
    s = s.replace(/est\b/g, '').replace(/ye\b/g, 'the').replace(/vpon\b/g, 'upon')
    s = s.replace(/vp\b/g, 'up').replace(/hath\b/g, 'has').replace(/saith\b/g, 'says')
    s = s.replace(/vnto\b/g, 'unto')
  }
  if (!variation.includes('grammar')) {
    s = s.replace(/\b(and|the|a|an|of|in|was|were|is|be|it|that|he|his|her|their|there|then|so|now|but|for|with|on|upon|over|from|by|at|to|into)\b/g, ' ')
  }
  return s.replace(/\s+/g, ' ').trim()
}

// ── Badge color (stable hash on witness ID) ─────────────────────────────────
const BADGE_COLORS = ['cb0', 'cb1', 'cb2', 'cb3', 'cb4', 'cb5']
export function badgeClass(wi, id) {
  if (!id) return BADGE_COLORS[wi % 6]
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = ((hash << 5) - hash) + id.charCodeAt(i)
  return BADGE_COLORS[Math.abs(hash) % 6]
}

// ── TEI file parsing (browser-side) ─────────────────────────────────────────
export function parseTEI(content, filename) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(content, 'application/xml')
  const NS = 'http://www.tei-c.org/ns/1.0'
  const XML_NS = 'http://www.w3.org/XML/1998/namespace'
  const getTag = tag => doc.getElementsByTagNameNS(NS, tag)[0] || doc.getElementsByTagName(tag)[0]
  const getAllTags = tag => [...doc.getElementsByTagNameNS(NS, tag), ...doc.getElementsByTagName(tag)]

  const titleEl = getTag('title')
  const idnoEl = getTag('idno')
  const dateEl = getTag('origDate') || getTag('date')
  const placeEl = getTag('origPlace') || getTag('settlement') || getTag('pubPlace')
  const sourceEl = getTag('repository') || getTag('bibl')
  const geoEl = getTag('geo')
  const affilEl = getAllTags('note').find(n => n.getAttribute('type') === 'affiliation')

  let year = null
  if (dateEl) {
    const m = (dateEl.getAttribute('when') || dateEl.textContent || '').match(/\d{4}/)
    if (m) year = parseInt(m[0])
  }

  let rawName = filename.replace(/\.[^.]+$/, '')
  if (titleEl && idnoEl?.textContent) rawName = `${titleEl.textContent.trim()} (${idnoEl.textContent.trim()})`
  else if (titleEl?.textContent) rawName = titleEl.textContent.trim()

  const country = placeEl?.textContent.trim() || ''
  const affiliation = affilEl?.textContent.trim() || ''
  const source = sourceEl?.textContent.trim() || ''
  let lat = 0, lng = 0
  if (geoEl?.textContent) {
    const coords = geoEl.textContent.trim().split(/\s+/)
    if (coords.length >= 2) { lat = parseFloat(coords[0]) || 0; lng = parseFloat(coords[1]) || 0 }
  }

  const segments = {}
  ;['p', 'lg', 'l', 'ab'].forEach(tag => {
    getAllTags(tag).forEach(el => {
      const id = el.getAttributeNS(XML_NS, 'id') || el.getAttribute('xml:id') || el.getAttribute('id')
      if (id) segments[id] = el.textContent.replace(/\s+/g, ' ').trim()
    })
  })
  if (!Object.keys(segments).length) {
    getAllTags('p').forEach((p, i) => {
      segments[`seg-${String(i + 1).padStart(3, '0')}`] = p.textContent.replace(/\s+/g, ' ').trim()
    })
  }

  return { name: rawName, year: year || 1500, country, affiliation, source, lat, lng, segments }
}

export function parsePlainText(content, filename) {
  const name = filename.replace(/\.[^.]+$/, '')
  const segments = {}
  content.split(/\n+/).map(l => l.trim()).filter(Boolean).forEach((l, i) => {
    segments[`seg-${String(i + 1).padStart(3, '0')}`] = l
  })
  return { name, year: 1500, segments }
}

export function parseCSV(content) {
  const lines = content.trim().split('\n')
  const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''))
  return lines.slice(1).map(line => {
    const vals = line.match(/(".*?"|[^,]+)(?=,|$)/g) || line.split(',')
    const obj = {}
    headers.forEach((h, i) => { obj[h] = (vals[i] || '').replace(/"/g, '').trim() })
    return obj
  })
}
