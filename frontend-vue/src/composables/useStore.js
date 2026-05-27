import { ref, computed } from 'vue'
import { WITNESSES, VARIANT_WORDS, COL_TEXTS, getColT } from '../data.js'

// ── Singleton state (module-level so all components share the same instance) ─
const witnesses = ref([...WITNESSES])
const selectedWit = ref('WEB')
const selectedVariant = ref('formless')
const variants = ref([...VARIANT_WORDS])
const witSearch = ref('')

// Collation text cache — populated from real data after upload
// Maps witness id → array of segment texts
const colTextCache = ref({ ...COL_TEXTS })

// Real alignment matrix from the backend (null until an alignment has run).
// Shape: { anchor_id, witnesses:[ids], anchor_lines:[{n,text}], cells:{id:[{score,text}|null]} }
const alignMatrix = ref(null)

function getSegText(id, si) {
  // If a real alignment matrix is loaded, read text from it (anchor-indexed rows)
  const m = alignMatrix.value
  if (m) {
    const cell = m.cells[id] ? m.cells[id][si] : null
    return cell ? cell.text : ''
  }
  const cache = colTextCache.value
  if (cache[id])
    return Array.isArray(cache[id]) ? cache[id][si] || '' : Object.values(cache[id])[si] || ''
  return getColT(id, si)
}

// Similarity score for a cell when a real matrix is loaded (else null → caller falls back)
function getAlignScore(id, si) {
  const m = alignMatrix.value
  if (!m) return null
  const cell = m.cells[id] ? m.cells[id][si] : null
  return cell ? cell.score : 0 // 0 = gap (no aligned line here)
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
    alignMatrix,
    getSegText,
    getAlignScore,
  }
}
