// ── Similarity ─────────────────────────────────────────────────────────────
export function jaccard(a, b) {
  const sa = new Set(
    a
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/),
  )
  const sb = new Set(
    b
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/),
  )
  let inter = 0
  for (const w of sa) if (sb.has(w)) inter++
  return inter / (sa.size + sb.size - inter || 1)
}

// ── Word-level similarity (for variant-graph grouping) ─────────────────────
export function levenshtein(a, b) {
  const m = a.length,
    n = b.length
  if (!m) return n
  if (!n) return m
  const dp = Array.from({ length: m + 1 }, () => Array.from({ length: n + 1 }).fill(0))
  for (let i = 0; i <= m; i++) dp[i][0] = i
  for (let j = 0; j <= n; j++) dp[0][j] = j
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    }
  }
  return dp[m][n]
}

// Normalized similarity in [0,1]; 1 = identical, 0 = completely different.
export function wordSimilarity(a, b) {
  if (!a && !b) return 1
  if (!a || !b) return 0
  const dist = levenshtein(a.toLowerCase(), b.toLowerCase())
  return 1 - dist / Math.max(a.length, b.length)
}

// Groups witnesses at a single collation position into variant clusters:
// witnesses whose readings are similar enough (>= threshold) end up in the
// same group, using connected components (readings don't need to be pairwise
// similar to *everything* in the group, just chained together transitively).
// currentReading: { witnessId: word }.
export function groupPositionBySimilarity(currentReading, witnessIds, threshold) {
  const paired = {}
  witnessIds.forEach((w) => (paired[w] = new Set([w])))
  for (let i = 0; i < witnessIds.length; i++) {
    for (let j = i + 1; j < witnessIds.length; j++) {
      const a = witnessIds[i],
        b = witnessIds[j]
      if (wordSimilarity(currentReading[a], currentReading[b]) < threshold) continue
      paired[a].add(b)
      paired[b].add(a)
    }
  }

  const visited = new Set()
  const groups = []
  witnessIds.forEach((wit) => {
    if (visited.has(wit)) return
    const group = new Set()
    const stack = [wit]
    while (stack.length) {
      const current = stack.pop()
      if (visited.has(current)) continue
      visited.add(current)
      group.add(current)
      paired[current].forEach((connected) => {
        if (!visited.has(connected)) stack.push(connected)
      })
    }
    groups.push([...group])
  })

  return groups.map((group) => {
    const counts = {}
    group.forEach((w) => {
      const word = currentReading[w]
      counts[word] = (counts[word] || 0) + 1
    })
    let representative = currentReading[group[0]] || '-'
    let best = -1
    for (const [word, c] of Object.entries(counts)) {
      if (c > best) {
        best = c
        representative = word
      }
    }
    return { representative: representative || '-', translations: group }
  })
}

// ── UPGMA dendrogram ────────────────────────────────────────────────────────
export function upgma(ids, getTextFn, sampleIndices = null) {
  const n = ids.length
  // Which segment indices to sample for the distance. Default: first 8.
  // Callers with a real alignment can pass indices spread across the whole range.
  const samples = sampleIndices && sampleIndices.length ? sampleIndices : [0, 1, 2, 3, 4, 5, 6, 7]
  const dist = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => {
      if (i === j) return 0
      let s = 0,
        counted = 0
      for (const k of samples) {
        const a = getTextFn(ids[i], k),
          b = getTextFn(ids[j], k)
        // Only count positions where at least one witness has text, so gaps
        // don't wash every pair out to "equally dissimilar".
        if (a || b) {
          s += jaccard(a, b)
          counted++
        }
      }
      return counted ? 1 - s / counted : 1
    }),
  )

  let nodes = ids.map((id, i) => ({
    id,
    i,
    left: null,
    right: null,
    h: 0,
    leaves: [i],
  }))
  let act = [...Array.from({ length: n }).keys()]
  const sz = Array.from({ length: n }).fill(1)

  while (act.length > 1) {
    let md = Infinity,
      pi = -1,
      pj = -1
    for (let ii = 0; ii < act.length; ii++)
      for (let jj = ii + 1; jj < act.length; jj++)
        if (dist[act[ii]][act[jj]] < md) {
          md = dist[act[ii]][act[jj]]
          pi = ii
          pj = jj
        }

    const i = act[pi],
      j = act[pj]
    const m = {
      id: `[${nodes[i].id}+${nodes[j].id}]`,
      i: nodes.length,
      left: nodes[i],
      right: nodes[j],
      h: Math.max(md / 2, nodes[i].h + 0.1, nodes[j].h + 0.1),
      leaves: [...nodes[i].leaves, ...nodes[j].leaves],
    }
    nodes.push(m)
    const ni = nodes.length - 1
    for (let k = 0; k <= ni; k++) {
      if (!dist[k]) dist[k] = []
      dist[k][ni] = 0
    }
    dist[ni] = Array.from({ length: ni + 1 }).fill(0)
    for (const k of act) {
      if (k === i || k === j) continue
      const d = (dist[i][k] * sz[i] + dist[j][k] * sz[j]) / (sz[i] + sz[j])
      dist[ni][k] = dist[k][ni] = d
    }
    sz.push(sz[i] + sz[j])
    act = act.filter((k) => k !== i && k !== j).concat([ni])
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
    s = s
      .replace(/est\b/g, '')
      .replace(/ye\b/g, 'the')
      .replace(/vpon\b/g, 'upon')
    s = s
      .replace(/vp\b/g, 'up')
      .replace(/hath\b/g, 'has')
      .replace(/saith\b/g, 'says')
    s = s.replace(/vnto\b/g, 'unto')
  }
  if (!variation.includes('grammar')) {
    s = s.replace(
      /\b(and|the|a|an|of|in|was|were|is|be|it|that|he|his|her|their|there|then|so|now|but|for|with|on|upon|over|from|by|at|to|into)\b/g,
      ' ',
    )
  }
  return s.replace(/\s+/g, ' ').trim()
}

// ── Badge color (stable hash on witness ID) ─────────────────────────────────
const BADGE_COLORS = ['cb0', 'cb1', 'cb2', 'cb3', 'cb4', 'cb5']
// Saturated accent colors matching each .col-badge.cbN border-color in CollationView's
// styles, so other views (e.g. the variant graph) can render witnesses in the same hue.
const BADGE_ACCENTS = ['#999999', '#e09880', '#88c480', '#80a8d4', '#d4c464', '#b490cc']

function badgeIndex(wi, id) {
  if (!id) return wi % 6
  let hash = 0
  for (let i = 0; i < id.length; i++) hash = (hash << 5) - hash + id.charCodeAt(i)
  return Math.abs(hash) % 6
}

export function badgeClass(wi, id) {
  return BADGE_COLORS[badgeIndex(wi, id)]
}

export function witnessColor(id) {
  return BADGE_ACCENTS[badgeIndex(0, id)]
}

// ── TEI file parsing (browser-side) ─────────────────────────────────────────
export function parseTEI(content, filename) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(content, 'application/xml')
  const NS = 'http://www.tei-c.org/ns/1.0'
  const XML_NS = 'http://www.w3.org/XML/1998/namespace'
  const getTag = (tag) => doc.getElementsByTagNameNS(NS, tag)[0] || doc.getElementsByTagName(tag)[0]
  const getAllTags = (tag) => [
    ...doc.getElementsByTagNameNS(NS, tag),
    ...doc.getElementsByTagName(tag),
  ]

  const titleEl = getTag('title')
  const authorEl = getTag('author')
  const idnoEl = getTag('idno')
  const dateEl = getTag('origDate') || getTag('date')
  const placeEl = getTag('origPlace') || getTag('settlement') || getTag('pubPlace')
  const sourceEl = getTag('repository') || getTag('bibl')
  const geoEl = getTag('geo')
  const affilEl = getAllTags('note').find((n) => n.getAttribute('type') === 'affiliation')
  const msDescEl = getTag('msDesc')

  // Witness id: prefer the filename prefix (before first '-' or '.'), it is the
  // most consistent identifier across a corpus. Fall back to msDesc/@xml:id.
  const fileStem = filename.replace(/\.[^.]+$/, '')
  let id = fileStem.split(/[-.]/)[0].trim()
  if (!id && msDescEl)
    id = msDescEl.getAttributeNS(XML_NS, 'id') || msDescEl.getAttribute('xml:id') || ''

  let year = null
  if (dateEl) {
    const m = (dateEl.getAttribute('when') || dateEl.textContent || '').match(/\d{3,4}/)
    if (m) year = parseInt(m[0])
  }

  // Display name: prefer "<title> (<idno>)", then title, then author, then filename
  let rawName = fileStem
  if (titleEl?.textContent && idnoEl?.textContent)
    rawName = `${titleEl.textContent.trim()} (${idnoEl.textContent.trim()})`
  else if (titleEl?.textContent) rawName = titleEl.textContent.trim()
  else if (authorEl?.textContent) rawName = authorEl.textContent.trim()

  const country = placeEl?.textContent.trim() || ''
  const affiliation = affilEl?.textContent.trim() || ''
  const source = sourceEl?.textContent.trim() || ''
  const author = authorEl?.textContent.trim() || ''
  let lat = 0,
    lng = 0
  if (geoEl?.textContent) {
    const coords = geoEl.textContent.trim().split(/[\s,]+/)
    if (coords.length >= 2) {
      lat = parseFloat(coords[0]) || 0
      lng = parseFloat(coords[1]) || 0
    }
  }

  const segments = {}
  ;['p', 'lg', 'l', 'ab'].forEach((tag) => {
    getAllTags(tag).forEach((el) => {
      const sid =
        el.getAttributeNS(XML_NS, 'id') || el.getAttribute('xml:id') || el.getAttribute('id')
      if (sid) segments[sid] = el.textContent.replace(/\s+/g, ' ').trim()
    })
  })
  if (!Object.keys(segments).length) {
    getAllTags('p').forEach((p, i) => {
      segments[`seg-${String(i + 1).padStart(3, '0')}`] = p.textContent.replace(/\s+/g, ' ').trim()
    })
  }

  // Track which fields were genuinely found, so the UI can show what was auto-detected
  const detected = {
    year: year !== null,
    country: !!country,
    source: !!source,
    coords: !!(lat || lng),
  }

  return {
    id,
    name: rawName,
    author,
    year,
    country,
    affiliation,
    source,
    lat,
    lng,
    segments,
    detected,
  }
}

export function parsePlainText(content, filename) {
  const fileStem = filename.replace(/\.[^.]+$/, '')
  const id = fileStem.split(/[-.]/)[0].trim()
  const segments = {}
  content
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((l, i) => {
      segments[`seg-${String(i + 1).padStart(3, '0')}`] = l
    })
  return {
    id,
    name: fileStem,
    year: null,
    country: '',
    affiliation: '',
    source: '',
    lat: 0,
    lng: 0,
    segments,
    detected: {},
  }
}

export function parseCSV(content) {
  const lines = content.trim().split('\n')
  const headers = lines[0].split(',').map((h) => h.trim().replace(/"/g, ''))
  return lines.slice(1).map((line) => {
    const vals = line.match(/(".*?"|[^,]+)(?=,|$)/g) || line.split(',')
    const obj = {}
    headers.forEach((h, i) => {
      obj[h] = (vals[i] || '').replace(/"/g, '').trim()
    })
    return obj
  })
}
