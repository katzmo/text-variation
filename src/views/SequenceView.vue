<script setup>
import { ref } from 'vue'
import { useStorage } from '@vueuse/core'
import TextSequence from '@/components/TextSequence.vue'
import { useZoom } from '@/composables/zoom'

const documents = useStorage('documents', [], localStorage)
const zoomWrapper = ref(null)
useZoom(zoomWrapper)
</script>

<template>
  <div id="sequences" ref="zoomWrapper">
    <TextSequence
      v-for="(doc, index) in documents"
      :key="index"
      :xmlString="doc.content"
    ></TextSequence>
  </div>
</template>

<style>
#sequences {
  --zoom-level: 0.5;
  --text-color: var(--color-text);
  display: flex;
  column-gap: max(1%, 1rem);
  padding-left: max(1%, 1rem);
  padding-right: max(1%, 1rem);
  overflow: scroll;
  cursor: default;
  max-height: 90vh;

  tei-header,
  tei-teiheader,
  tei-figure,
  tei-note,
  tei-front,
  tei-back {
    display: none;
  }
}
</style>
