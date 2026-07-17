<script setup>
import { ref } from 'vue'
import { useCETEI } from '@/composables/cetei'

const props = defineProps({
  xmlString: String,
})

const display = ref()
const { appendXmlString } = useCETEI()

appendXmlString(display, props.xmlString)
</script>

<template>
  <div ref="display"></div>
</template>
