import { ref, computed } from 'vue'
import { WITNESSES, VARIANT_WORDS, COL_TEXTS, getColT } from '../data.js'

// ── Singleton state (module-level so all components share the same instance) ─
const witnesses      = ref([...WITNESSES])
const selectedWit    = ref('WEB')
const selectedVariant= ref('formless')
const variants       = ref([...VARIANT_WORDS])
const witSearch      = ref('')

// Collation text cache — populated from real data after upload
// Maps witness id → array of segment texts
const colTextCache   = ref({ ...COL_TEXTS })

function getSegText(id, si) {
  const cache = colTextCache.value
  if (cache[id]) return Array.isArray(cache[id]) ? cache[id][si] || '' : Object.values(cache[id])[si] || ''
  return getColT(id, si)
}

const filteredWitnesses = computed(() => {
  const q = witSearch.value.toLowerCase()
  if (!q) return witnesses.value
  return witnesses.value.filter(w =>
    w.id.toLowerCase().includes(q) || w.name.toLowerCase().includes(q)
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
    getSegText,
  }
}
