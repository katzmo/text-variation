<script setup>
import { onMounted, ref } from 'vue'
import CETEI from 'CETEIcean'

const props = defineProps({
  xmlString: String,
})

const display = ref()

onMounted(async () => {
  const CETEIcean = new CETEI({ ignoreFragmentId: true })
  CETEIcean.addBehaviors({
    tei: {
      // Display document ID
      TEI: (el) => {
        const xmlId = el.getAttribute('xml:id')
        if (xmlId) {
          el.insertAdjacentHTML('afterbegin', `<div class="identifier">${xmlId}</div>`)
        }
      },
      // Render line breaks
      lb: ['<br>'],
      // Display a reason in gaps
      gap: ['<span class="reason">$@reason</span>'],
      // Display header information
      teiHeader: null,
    },
  })
  if (props.xmlString) {
    CETEIcean.makeHTML5(props.xmlString, (data) => {
      display.value.appendChild(data)
    })
  }
})
</script>

<template>
  <div class="text-sequence" ref="display"></div>
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

  .text-segment {
    display: block;
    text-align: justify;
    padding: 0.5em;
    margin-top: 1em;
    background-color: var(--color-background-soft);
    transition: filter 400ms ease-in-out;
  }

  .identifier {
    background-color: var(--color-background);
    font-size: max(75%, 100% * var(--zoom-level));
    text-align: center;
    position: sticky;
    top: 0;
  }
}
</style>
