<script setup>
import { ref } from 'vue'
import Modal from '@/components/Modal.vue'
import IconDocument from './icons/IconDocument.vue'

const props = defineProps({
  document: Object,
})

const isModalOpen = ref(false)
</script>

<template>
  <li>
    <span>{{ document.name }}</span>
    <span
      ><button @click="isModalOpen = true" aria-label="view document">
        <IconDocument aria-hidden /></button
    ></span>
  </li>
  <Modal v-model="isModalOpen">
    <h2>{{ document.name }}</h2>
    <div class="source">
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

button {
  --color-button: none;
  --color-button-hover: none;
  --color-button-active: none;
  color: var(--color-text);
  font-size: 0.75em;
  padding: 0.25em 0.5em;
}

.source {
  max-width: 50rem;
  white-space: preserve;
  font-family: monospace;
  margin: var(--margin);
}
</style>
