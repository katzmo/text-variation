<script setup>
import { ref } from 'vue'
import { useCETEI } from '@/composables/cetei'

const props = defineProps({
  name: String,
  xmlString: String,
})

const display = ref()
const { appendXmlString } = useCETEI()

appendXmlString(display, props.xmlString)
</script>

<template>
  <div class="text-sequence" ref="display">
    <div class="identifier">{{ name }}</div>
  </div>
</template>

<style>
.text-sequence {
  margin-bottom: auto;
  transition: margin 0.3s ease;

  tei-teiheader,
  tei-text {
    display: block;
    zoom: var(--zoom-level);
    font-size: clamp(33%, 100% * var(--zoom-level), 100%);
    color: rgba(50, 50, 50, var(--zoom-level));
    min-width: 22em;
    max-width: 100em;
    margin-left: auto;
    margin-right: auto;
  }

  .text-segment,
  [data-id] {
    display: block;
    text-align: justify;
    padding: 0.5em;
    margin-top: 1em;
    background-color: var(--color-background-soft);
    transition: filter 400ms ease-in-out;
  }

  .highlighted:not(.aligned) {
    filter: brightness(0.8);
  }

  .aligned {
    outline: 0.25rem solid var(--color-border-hover);
    outline-offset: 0.5rem;
    border-radius: var(--border-radius);
    position: relative;
    z-index: 1;
  }

  .identifier {
    background-color: var(--color-background);
    font-size: max(75%, 100% * var(--zoom-level));
    text-align: center;
    margin-bottom: 0.5rem;
    position: sticky;
    z-index: 10;
    top: 0;
  }
}
</style>
