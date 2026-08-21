import { ref, computed } from 'vue'
import { WITNESSES, VARIANT_WORDS, COL_TEXTS, getColT } from '../data.js'

// ── Singleton state (module-level so all components share the same instance) ─
const witnesses = ref([...WITNESSES])
const selectedWit = ref(null)
const selectedVariant = ref('formless')
const variants = ref([...VARIANT_WORDS])
const witSearch = ref('')

// Collation text cache — populated from real data after upload
// Maps witness id → array of segment texts
const colTextCache = ref({ ...COL_TEXTS })

// Real alignment scores from the backend (null until an alginment has run).
// Shape: {witness_id: [seg_id, text, scores: [seg_id, witness, score]]}
const alignScores = ref(null)

function getSegText(id, si) {
  // If a real alignment matrix is loaded, read text from it (anchor-indexed rows)
  const s = alignScores.value
  if (s) {
    return s[id]?.[si].text ?? ''
  }
  const cache = colTextCache.value
  if (cache[id])
    return Array.isArray(cache[id]) ? cache[id][si] || '' : Object.values(cache[id])[si] || ''
  return getColT(id, si)
}

// Similarity score for a segment when real scores are loaded (else null → caller falls back)
function getAlignScore(id, si) {
  const scores = alignScores.value
  if (!scores) return null
  const segScores = scores[id][si].scores
  // No matching segments
  if (!segScores.length) return 0
  // Similarity to reference
  if (selectedWit.value) {
    return segScores.find((s) => s.witness === selectedWit.value)?.score ?? 0
  }
  // Average similarity to all matching segments
  return (
    segScores.reduce(
      (sum, s) =>
        filteredWitnesses.value.map((w) => w.id).includes(s.witness) ? sum + s.score : sum,
      0,
    ) / segScores.length
  )
}

function getAlignedSegs(segId) {
  const { id, si } = splitSegId(segId)
  if (alignScores.value) {
    const alignedSegs = { [id]: si }
    for (const s of alignScores.value[id][si].scores) {
      alignedSegs[s.witness] = splitSegId(s.seg_id).si
    }
    return alignedSegs
  }
  // Fallback to aligning to the same segment index.
  return Object.fromEntries(filteredWitnesses.value.map((w) => [w.id, si]))
}

// Stable segment ID for a cell, matching the backend's "{witness_id}:{anchor_pos}" scheme.
function getSegId(id, si) {
  const s = alignScores.value
  const cell = s && s[id] ? s[id][si] : null
  return cell && cell.seg_id ? cell.seg_id : `${id}:${si}`
}

// Split a segment ID up into {witness ID, selector, segment index}.
function splitSegId(segId) {
  const parts = segId.split(':')
  const [id, unit, si] = parts.length === 3 ? parts : [parts[0], '', parts[1]]
  return { id, unit, si }
}

const filteredWitnesses = computed(() => {
  const q = witSearch.value.toLowerCase()
  if (!q) return witnesses.value
  return witnesses.value.filter(
    (w) => w.id.toLowerCase().includes(q) || w.name.toLowerCase().includes(q),
  )
})

export function useStore() {
  return {
    witnesses,
    selectedWit,
    selectedVariant,
    variants,
    witSearch,
    filteredWitnesses,
    colTextCache,
    alignScores,
    getSegText,
    getAlignScore,
    getAlignedSegs,
    getSegId,
    splitSegId,
  }
}
