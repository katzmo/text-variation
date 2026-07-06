<script setup>
import { ref } from 'vue'
import Modal from '@/components/Modal.vue'
import DocumentTei from '@/components/DocumentTei.vue'
import IconDocument from './icons/IconDocument.vue'

const props = defineProps({
  document: Object,
})

const isModalOpen = ref(false)
const isSource = ref(false)
</script>

<template>
  <li>
    <span>{{ document.name }}</span>
    <span>
      <button @click="isModalOpen = true" aria-label="view document">
        <IconDocument aria-hidden />
      </button>
    </span>
  </li>
  <Modal v-model="isModalOpen">
    <nav>
      <button v-if="!isSource" @click="isSource = true">View source</button>
      <button v-if="isSource" @click="isSource = false">View text</button>
    </nav>
    <h2>{{ document.name }}</h2>
    <DocumentTei v-if="!isSource" :xmlString="document.content" class="text" />
    <div v-if="isSource" class="source">
      <code>{{ document.content }}</code>
    </div>
  </Modal>
</template>

<style scoped>
li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  padding: 0.5em 0;
}

li button {
  --color-button: none;
  --color-button-hover: none;
  --color-button-active: none;
  color: var(--color-text);
  font-size: 0.75em;
  padding: 0.25em 0.5em;
}

.text,
.source {
  max-width: 50rem;
  margin: var(--margin);
}

.source {
  white-space: preserve;
  font-family: monospace;
}
</style>
