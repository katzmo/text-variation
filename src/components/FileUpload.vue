<script setup>
import { ref, watch } from 'vue'
import { useFileDialog, useDropZone } from '@vueuse/core'
import { useIndexedDBStore } from '@/composables/db'
import { useAlignmentProcessor } from '@/composables/processAlignment'
import { useDocumentProcessor } from '@/composables/processDocument'
import IconWaiting from './icons/IconWaiting.vue'

const emit = defineEmits(['close-modal', 'documents-updated'])

const message = ref()
const isProcessing = ref(false)

const { documents, dbExec } = useIndexedDBStore()
const { parseXML, segmentXML, applyGroups, saveSegments } = useDocumentProcessor()
const { alignSegments } = useAlignmentProcessor()

// File dialog for browsing
const {
  files: selectedFiles,
  open: openFileDialog,
  reset: resetFileDialog,
} = useFileDialog({
  accept: '.xml',
  multiple: true,
})

// Drop zone logic
const dropZoneRef = ref(null)
const { isOverDropZone } = useDropZone(dropZoneRef, {
  onDrop: (files) => processFiles(files),
  dataTypes: ['text/xml'],
  multiple: true,
})

// Handle file selection from dialog
watch(selectedFiles, (newFiles) => {
  if (newFiles) processFiles(newFiles)
  resetFileDialog()
})

/**
 * Process uploaded files from dialog or drop and save them.
 *
 * @param {Array} fileList - Uploaded files
 * @returns {Promise<void>} - Promise that esolves when all files have been processed.
 * @emits documents-updated
 */
const processFiles = async (fileList) => {
  isProcessing.value = true
  await Promise.all(
    Array.from(fileList).map(async (file) => {
      const content = await readFileAsText(file)
      const doc = {
        id: file.name.split('.', 1)[0],
        name: file.name,
        size: file.size,
        content,
      }
      const xml = parseXML(doc)
      segmentXML(xml, doc)
      doc.key = await dbExec('documents', 'add', doc)
      if (!doc.key) {
        message.value = `Error uploading ${file.name}: ${doc.id} already exists.`
        return
      }
      await saveSegments(xml, doc)
    }),
  )
  isProcessing.value = false
  emit('documents-updated', documents.value)
}

/**
 * Read a file as text.
 *
 * @param file - The file to read.
 * @returns {Promise<string>} - Promise that resolves with the text.
 */
const readFileAsText = (file) => {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target.result)
    reader.readAsText(file)
  })
}

/**
 * Remove a file from upload.
 *
 * @param {number} id - ID of the file to remove.
 * @returns {Promise<void>} - Resolves when file has been deleted.
 * @emits documents-updated
 */
const removeFile = async (key) => {
  await dbExec('documents', 'delete', key)
  emit('documents-updated', documents.value)
}

/**
 * Clear all files from upload.
 *
 * @returns {Promise<void>} - Resolves when the table has been cleared.
 * @emits documents-updated
 */
const clearFiles = async () => {
  await dbExec('documents', 'clear')
  emit('documents-updated', documents.value)
}

/**
 * Save matching segment groups and scores.
 *
 * @returns {Promise<void>} - Resolves when groups and scores have been saved.
 * @emits close-modal
 */
const runAlignment = async () => {
  isProcessing.value = true
  await alignSegments()
  await Promise.all(
    documents.value.map(async (doc) => {
      const xml = parseXML(doc)
      await applyGroups(xml, doc)
      return await dbExec('documents', 'put', { ...doc })
    }),
  )
  isProcessing.value = false
  emit('close-modal')
}
</script>

<template>
  <div class="file-upload">
    <div class="drop-area" :class="{ 'drag-over': isOverDropZone }" ref="dropZoneRef">
      <p>Drag & drop TEI files here or click to upload</p>
      <button @click="openFileDialog" class="button">Upload Files</button>
    </div>
    <div v-if="message" class="error message">{{ message }}</div>
    <div v-if="documents.length > 0" class="file-list">
      <button @click="clearFiles" class="clear">Clear All</button>
      <h3>Uploaded Files:</h3>
      <ul>
        <li v-for="file in documents" :key="file.key" class="file-item">
          <span>{{ file.name }} ({{ Math.round(file.size / 1000) }} kB)</span>
          <button @click="removeFile(file.key)" class="remove" aria-label="remove file">
            &times;
          </button>
        </li>
      </ul>
    </div>
  </div>
  <button v-if="documents.length > 0" @click="runAlignment" :disabled="isProcessing">
    Run alignment
  </button>
  <div class="processing" v-if="isProcessing">
    <IconWaiting width="4em" aria-label="Processing documents." />
  </div>
</template>

<style scoped>
.drop-area {
  border: 2px dashed var(--color-border);
  padding: 3rem;
  text-align: center;
  transition: all 0.3s;
  margin-bottom: 1rem;
  background-color: var(--color-background-soft);
}

.drop-area.drag-over {
  border-color: var(--color-border-hover);
  background-color: var(--color-background-mute);
}

.file-item {
  padding: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.error {
  color: #ff4444;
  font-weight: bold;
}

button.remove,
button.clear {
  --color-button: none;
  --color-button-hover: none;
  --color-button-active: none;
  color: #ff4444;
  float: right;
}

button.clear:hover,
button.remove:hover {
  color: #cc0000;
}

button.remove {
  font-size: 1.5em;
  padding: 0em 0.5em;
  margin-top: -0.33rem;
}

.processing {
  display: flex;
  justify-content: center;
}
</style>
