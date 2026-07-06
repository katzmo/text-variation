<script setup>
import { ref } from 'vue'
import { useStorage } from '@vueuse/core'
import FileUploader from '@/components/FileUpload.vue'
import Modal from '@/components/Modal.vue'
import DocumentItem from '@/components/DocumentItem.vue'

const documents = useStorage('documents', [], localStorage)
const isModalOpen = ref(false)
</script>

<template>
  <h2>Documents</h2>
  <p><button @click="isModalOpen = true">Manage data</button></p>
  <Modal v-model="isModalOpen">
    <h2>Manage data</h2>
    <FileUploader />
    <button @click="isModalOpen = false">Done</button>
  </Modal>
  <ul class="no-list">
    <DocumentItem v-for="(doc, index) in documents" :key="index" :document="doc"></DocumentItem>
  </ul>
</template>
