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
  <div ref="display"></div>
</template>
