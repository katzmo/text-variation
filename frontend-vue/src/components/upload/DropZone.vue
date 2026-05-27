<template>
  <div>
    <div
      class="dropzone"
      :class="{ over: dropOver }"
      @dragover.prevent="dropOver = true"
      @dragleave="dropOver = false"
      @drop.prevent="onDrop"
    >
      <input type="file" multiple accept=".xml,.txt,.csv,.json" @change="onInput" />
      <div class="dropzone-icon">📄</div>
      <div class="dropzone-text">Drag & drop TEI XML or plain text files here</div>
      <div class="dropzone-hint">or click to browse · also accepts companion .csv</div>
    </div>

    <div class="file-list" v-if="files.length">
      <div class="file-item" v-for="(f, i) in files" :key="i">
        <span class="file-icon">{{ f.type === 'csv' ? '📋' : '📝' }}</span>
        <span class="file-name">{{ f.name }}</span>
        <span class="file-status" :class="f.parsed ? 'ok' : 'warn'">{{
          f.parsed ? `${f.segCount} segments` : 'pending'
        }}</span>
        <button class="file-remove" @click="remove(i)">✕</button>
      </div>
    </div>

    <div class="companion-hint" v-if="hasCompanion">
      ✓ Companion metadata file detected — form will be pre-filled.
    </div>
    <div
      class="companion-hint"
      v-else-if="files.length"
      style="background: #fdf8ee; border-color: #e0d090; color: #6a5a10"
    >
      💡 Add a <strong>.csv</strong> with columns
      <code>id, name, year, country, lat, lng, affiliation, source</code> to skip the metadata form.
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { parseTEI, parsePlainText } from '../../utils.js'

const props = defineProps({ files: Array })
const emit = defineEmits(['update:files'])
const dropOver = ref(false)

const hasCompanion = computed(() => props.files.some((f) => f.type === 'csv' || f.type === 'json'))

async function readFile(file) {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = (e) => res(e.target.result)
    r.onerror = rej
    r.readAsText(file)
  })
}

async function addFiles(fileList) {
  const current = [...props.files]
  for (const file of fileList) {
    const ext = file.name.split('.').pop().toLowerCase()
    const content = await readFile(file)
    const type = ['csv', 'json'].includes(ext) ? ext : ext === 'xml' ? 'xml' : 'txt'
    let parsed = false,
      segCount = 0,
      segments = {},
      meta = null
    if (type === 'xml') {
      meta = parseTEI(content, file.name)
      segments = meta.segments
      segCount = Object.keys(segments).length
      parsed = true
    } else if (type === 'txt') {
      meta = parsePlainText(content, file.name)
      segments = meta.segments
      segCount = Object.keys(segments).length
      parsed = true
    }
    current.push({ name: file.name, type, content, parsed, segCount, segments, meta })
  }
  emit('update:files', current)
}

function onInput(e) {
  addFiles(e.target.files)
}
function onDrop(e) {
  dropOver.value = false
  addFiles(e.dataTransfer.files)
}
function remove(i) {
  const f = [...props.files]
  f.splice(i, 1)
  emit('update:files', f)
}
</script>

<style scoped>
.dropzone {
  border: 2px dashed var(--border2);
  border-radius: 8px;
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
  position: relative;
}
.dropzone:hover,
.dropzone.over {
  border-color: var(--ink);
  background: var(--bg-hover);
}
.dropzone input[type='file'] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
  height: 100%;
}
.dropzone-icon {
  font-size: 32px;
  margin-bottom: 8px;
}
.dropzone-text {
  font-size: 13px;
  color: var(--ink2);
  margin-bottom: 4px;
}
.dropzone-hint {
  font-size: 11px;
  color: var(--ink3);
  font-family: var(--mono);
}
.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 14px;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  font-size: 12px;
}
.file-icon {
  font-size: 16px;
  flex-shrink: 0;
}
.file-name {
  flex: 1;
  font-family: var(--mono);
  font-size: 11px;
}
.file-status {
  font-size: 10px;
  font-family: var(--mono);
}
.file-status.ok {
  color: #4a9;
}
.file-status.warn {
  color: #c80;
}
.file-remove {
  width: 20px;
  height: 20px;
  border: none;
  background: none;
  cursor: pointer;
  color: var(--ink3);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
}
.file-remove:hover {
  background: var(--bg-hover);
  color: var(--ink);
}
.companion-hint {
  margin-top: 14px;
  padding: 10px 14px;
  background: #f0f7f0;
  border: 1px solid #c0dcc0;
  border-radius: 5px;
  font-size: 11px;
  color: #3a6a3a;
  font-family: var(--mono);
  line-height: 1.6;
}
</style>
