<template>
  <div class="upload-overlay" @click.self="$emit('close')">
    <div class="upload-modal">
      <div class="upload-modal-header">
        <span class="upload-modal-title">Upload witness texts</span>
        <button class="upload-modal-close" @click="$emit('close')">✕</button>
      </div>

      <!-- Step indicator -->
      <div class="upload-steps">
        <div v-for="(label, i) in ['Upload files','Edit metadata','Load texts','Align segments']" :key="i"
          class="upload-step" :class="{ active: step === i+1, done: step > i+1 }">
          <div class="step-num">{{ step > i+1 ? '✓' : i+1 }}</div>
          {{ label }}
        </div>
      </div>

      <div class="upload-body">
        <!-- Step 1: Drop files -->
        <DropZone v-if="step===1" v-model:files="files" />

        <!-- Step 2: Metadata -->
        <MetadataForm v-if="step===2" v-model:meta="meta" />

        <!-- Step 3: Processing / done -->
        <div v-if="step===3">
          <div class="processing" v-if="processing">
            <div class="spinner"></div>
            <div class="processing-text">{{ status }}</div>
          </div>
          <div v-else style="text-align:center;padding:32px;">
            <div style="font-size:32px;margin-bottom:12px;">✓</div>
            <div style="font-family:var(--serif);font-size:16px;font-weight:700;margin-bottom:8px;">{{ meta.length }} witnesses loaded</div>
            <div style="font-size:12px;color:var(--ink3);font-family:var(--mono);">Proceed to align segments, or skip to the dashboard.</div>
          </div>
        </div>

        <!-- Step 4: Alignment -->
        <AlignmentStep v-if="step===4" />
      </div>

      <div class="upload-footer">
        <button class="btn-secondary" v-if="step>1 && !processing && !(step===4)" @click="step--">← Back</button>
        <button class="btn-secondary" @click="$emit('close')">{{ step===4 ? 'Close' : 'Cancel' }}</button>
        <button class="btn-primary" v-if="step===1" :disabled="textFiles.length===0" @click="goToMeta">Next →</button>
        <button class="btn-primary" v-if="step===2" @click="loadTexts">Load texts →</button>
        <button class="btn-primary" v-if="step===3 && !processing" @click="goToAlign">Align segments →</button>
        <button class="btn-secondary" v-if="step===3 && !processing" @click="$emit('close')">Skip — go to dashboard</button>
        <button class="btn-primary" v-if="step===4" @click="$emit('close')">Done — view dashboard</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import DropZone from './DropZone.vue'
import MetadataForm from './MetadataForm.vue'
import AlignmentStep from './AlignmentStep.vue'
import { useStore } from '../../composables/useStore.js'
import { parseTEI, parsePlainText, parseCSV, upgma, leafOrder } from '../../utils.js'
import { postUploadFiles, postConfirmUpload, fetchWitnesses, fetchSegments } from '../../api.js'

defineEmits(['close'])
const { witnesses, selectedWit, variants, colTextCache } = useStore()

const step       = ref(1)
const files      = ref([])
const meta       = ref([])
const processing = ref(false)
const status     = ref('')

const textFiles = computed(() => files.value.filter(f => f.type === 'xml' || f.type === 'txt'))

async function goToMeta() {
  const csvFile = files.value.find(f => f.type === 'csv')
  const csvRows = csvFile ? parseCSV(csvFile.content) : []
  meta.value = textFiles.value.map((f, i) => {
    const m = f.meta || {}
    const fallbackId = f.name.replace(/\.[^.]+$/, '').split(/[-.]/)[0].trim()
    const id = (m.id || fallbackId || `W${i + 1}`).toUpperCase()
    const csv = csvRows.find(r => (r.id || '').toUpperCase() === id) || csvRows[i] || {}
    return {
      id:   csv.id || id,
      name: csv.name || m.name || f.name,
      year: parseInt(csv.year || m.year || '') || null,
      country:     csv.country || m.country || '',
      lat:         parseFloat(csv.lat ?? m.lat ?? 0) || 0,
      lng:         parseFloat(csv.lng ?? m.lng ?? 0) || 0,
      affiliation: csv.affiliation || m.affiliation || '',
      source:      csv.source || m.source || '',
      segments:    f.segments,
      filename:    f.name,
    }
  })
  if (csvFile && csvRows.length >= textFiles.value.length) { step.value = 3; await loadTexts() }
  else step.value = 2
}

async function loadTexts() {
  step.value = 3; processing.value = true; status.value = 'Processing…'
  let newWitnesses, newSegments
  try {
    status.value = 'Uploading to backend…'
    await postUploadFiles(textFiles.value, files.value.find(f => f.type === 'csv'))
    await postConfirmUpload(meta.value.map(m => ({ ...m })), true)
    status.value = 'Loading data…'
    const wData = await fetchWitnesses()
    const sData = await fetchSegments()
    newWitnesses = wData.map(w => ({ ...w, origin: [w.lat || 0, w.lng || 0] }))
    newSegments  = sData
  } catch(e) {
    status.value = 'Running client-side…'
    await new Promise(r => setTimeout(r, 500))
    newWitnesses = meta.value.map(m => ({ id: m.id, name: m.name, year: m.year, origin: [m.lat, m.lng], affiliation: m.affiliation, source: m.source, lat: m.lat, lng: m.lng, country: m.country }))
    newSegments  = meta.value.reduce((a, m) => { a[m.id] = m.segments; return a }, {})
  }

  // Update shared store
  witnesses.value   = newWitnesses
  selectedWit.value = newWitnesses[0]?.id || ''

  // Extract variants
  const wordFreq = {}
  meta.value.forEach(m => Object.values(m.segments).forEach(seg =>
    seg.toLowerCase().replace(/[^\w\s]/g,'').split(/\s+/).forEach(w => {
      if (w.length > 3) wordFreq[w] = (wordFreq[w] || 0) + 1
    })
  ))
  variants.value = Object.entries(wordFreq).filter(([,c]) => c > 1 && c < meta.value.length * 3).map(([w]) => w).sort().slice(0, 60)

  // Update collation text cache
  Object.entries(newSegments).forEach(([id, segs]) => { colTextCache.value[id] = Array.isArray(segs) ? segs : Object.values(segs) })

  processing.value = false
}

function goToAlign() { step.value = 4 }
</script>

<style scoped>
.upload-overlay { position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:600;display:flex;align-items:center;justify-content:center;padding:32px; }
.upload-modal { background:var(--bg-panel);border-radius:10px;box-shadow:0 12px 48px rgba(0,0,0,0.25);width:100%;max-width:780px;max-height:90vh;display:flex;flex-direction:column;overflow:hidden; }
.upload-modal-header { display:flex;align-items:center;padding:14px 20px;border-bottom:1px solid var(--border);flex-shrink:0; }
.upload-modal-title { font-family:var(--serif);font-size:15px;font-weight:700;flex:1; }
.upload-modal-close { width:28px;height:28px;border:1px solid var(--border2);border-radius:4px;background:var(--bg);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px;color:var(--ink3); }
.upload-modal-close:hover { background:var(--bg-hover); }
.upload-steps { display:flex;border-bottom:1px solid var(--border);flex-shrink:0; }
.upload-step { flex:1;padding:10px 16px;font-size:12px;color:var(--ink3);border-bottom:2px solid transparent;display:flex;align-items:center;gap:7px; }
.upload-step.active { color:var(--ink);border-bottom-color:var(--ink);font-weight:500; }
.step-num { width:20px;height:20px;border-radius:50%;background:var(--border);color:var(--ink3);font-family:var(--mono);font-size:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.upload-step.active .step-num { background:var(--ink);color:#fff; }
.upload-step.done .step-num { background:#4a9;color:#fff; }
.upload-body { flex:1;overflow-y:auto;padding:20px; }
.upload-footer { display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:14px 20px;border-top:1px solid var(--border);flex-shrink:0; }
.processing { display:flex;flex-direction:column;align-items:center;gap:16px;padding:40px; }
.processing-text { font-family:var(--mono);font-size:12px;color:var(--ink3); }
</style>
