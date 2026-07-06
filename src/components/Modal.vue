<script setup>
import { ref, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'

const props = defineProps({
  modelValue: Boolean,
})
const emit = defineEmits(['update:modelValue'])
const isOpen = ref(props.modelValue)

// Sync with parent
watch(
  () => props.modelValue,
  (val) => {
    isOpen.value = val
  },
)
watch(
  () => isOpen.value,
  (val) => {
    emit('update:modelValue', val)
    val ? document.body.classList.add('modal-open') : document.body.classList.remove('modal-open')
  },
)

/**
 * Close the modal.
 */
const close = () => {
  isOpen.value = false
}

// Close on escape key or click outside
onKeyStroke('Escape', close)
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" ref="overlay" @click.self="close">
        <div class="modal-content" role="dialog" aria-modal="true">
          <slot />
          <button class="modal-close" @click="close" aria-label="Close modal">&times;</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style>
body.modal-open {
  overflow: hidden;
}

body.modal-open #app {
  filter: blur(8px);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  position: relative;
  background: var(--color-background);
  padding: 2rem;
  border-radius: var(--border-radius);
  max-width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-close {
  --color-button: none;
  --color-button-hover: none;
  --color-button-active: none;
  color: inherit;
  font-size: 1.5em;
  padding: 0em 0.5em;
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
