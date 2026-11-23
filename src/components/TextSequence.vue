<script setup>
import { ref, watch } from 'vue'
import { useCETEI } from '@/composables/cetei'
import { useScores } from '@/composables/score'
import { useIndexedDBStore } from '@/composables/db'

const props = defineProps({
  docKey: Number,
  name: String,
  xmlString: String,
})

const display = ref()
const { appendXmlString } = useCETEI()
const { lastUpdated } = useIndexedDBStore()
const { updateScores } = useScores(display)

appendXmlString(display, props.xmlString)

watch([display, lastUpdated['scores']], () => {
  updateScores(props.docKey)
})
</script>

<template>
  <div class="text-sequence" ref="display">
    <div class="identifier">{{ name }}</div>
  </div>
</template>

<style>
.text-sequence {
  min-width: 3rem;
  margin-bottom: auto;
  transition: margin 0.3s ease;

  tei-teiheader,
  tei-text {
    display: block;
    zoom: var(--zoom-level);
    font-size: clamp(33%, 100% * var(--zoom-level), 100%);
    color: oklch(from var(--color-text) l c h / var(--zoom-level));
    min-width: 22em;
    max-width: 100em;
    margin-left: auto;
    margin-right: auto;
  }

  * {
    pointer-events: none;
  }

  .text-segment,
  [data-id] {
    --color-segment: var(--color-background-soft);
    display: block;
    text-align: justify;
    padding: 0.5em;
    margin-top: 1em;
    background-color: color-mix(
      var(--color-segment) calc(var(--bg-opacity) * 100%),
      var(--color-background-soft)
    );
    transition: filter 400ms ease-in-out;
    pointer-events: all;
  }

  .highlighted:not(.aligned),
  [data-id]:not(.aligned):hover {
    filter: brightness(0.8);
  }

  .aligned {
    outline: calc(0.25rem / var(--zoom-level)) solid var(--color-border-hover);
    outline-offset: 0.5rem;
    border-radius: var(--border-radius);
    position: relative;
    z-index: 1;
  }

  .identifier {
    background-color: var(--color-background);
    font-size: max(60%, 100% * var(--zoom-level));
    text-align: center;
    margin-bottom: 0.5rem;
    position: sticky;
    z-index: 10;
    top: 0;
  }

  tei-fw,
  tei-facsimile,
  :empty {
    display: none;
  }

  tei-row {
    display: block;
  }

  tei-cell {
    display: inline-block;
  }
}
</style>
