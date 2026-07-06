<script setup>
import { useStorage } from '@vueuse/core'
import TextSequence from '@/components/TextSequence.vue'

const documents = useStorage('documents', [], localStorage)
</script>

<template>
  <div id="sequences">
    <TextSequence
      v-for="(doc, index) in documents"
      :key="index"
      :xmlString="doc.content"
    ></TextSequence>
  </div>
</template>

<style>
#sequences {
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
