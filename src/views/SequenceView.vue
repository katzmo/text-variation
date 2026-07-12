<script setup>
import { onMounted, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import TextSequence from '@/components/TextSequence.vue'
import { useZoom } from '@/composables/zoom'
import { useAlignment } from '@/composables/align'
import { useIndexedDBStore } from '@/composables/db'

const { documents } = useIndexedDBStore()
const wrapper = ref(null)
const { currentZoom } = useZoom(wrapper)
const { alignedGroupId, alignSections, highlightSections, unhighlightSections } =
  useAlignment(wrapper)

onMounted(() => {
  // Add hover background
  wrapper.value.addEventListener('mouseover', (event) => {
    highlightSections(`[data-group="${event.target.dataset.group}"]`)
  })
  // Remove hover background
  wrapper.value.addEventListener('mouseout', (event) => {
    unhighlightSections(`[data-group="${event.target.dataset.group}"]`)
  })
  // Align sections
  wrapper.value.addEventListener('click', (event) => {
    const groupId = event.target.dataset.group
    if (groupId) alignedGroupId.value = groupId
  })
})

watch(alignedGroupId, (newId) => {
  alignSections(`[data-group="${newId}"]`, '.text-sequence', currentZoom.value)
})

watchDebounced(
  currentZoom,
  (newValue) => {
    if (alignedGroupId.value) {
      alignSections(`[data-group="${alignedGroupId.value}"]`, '.text-sequence', newValue, false)
    }
  },
  { debounce: 333 },
)
</script>

<template>
  <div id="sequences" ref="wrapper">
    <TextSequence
      v-for="doc in documents"
      :key="doc.key + doc.content.length.toString()"
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
