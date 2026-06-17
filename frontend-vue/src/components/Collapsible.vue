<script setup>
import { ref } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
})

const isOpen = ref(true)

const toggle = () => {
  isOpen.value = !isOpen.value
}
</script>

<template>
  <section :class="{ collapsible: true, open: isOpen }">
    <button @click="toggle" class="collapsible-header">
      <span>{{ title }}</span>
    </button>
    <Transition name="slide">
      <div v-if="isOpen" class="collapsible-content">
        <slot></slot>
      </div>
    </Transition>
  </section>
</template>

<style scoped>
.collapsible-header {
  width: 100%;
  padding: 1rem;
  background-color: var(--bg);
  border: none;
  cursor: pointer;
  display: flex;
  justify-content: flex-start;
  column-gap: 1rem;
  align-items: center;
  font-size: 16px;
  border-bottom: 1px solid var(--border);
}

.collapsible-header:hover {
  background-color: var(--bg-hover);
}

.collapsible-header::before {
  content: '';
  right: 15px;
  width: 8px;
  height: 8px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-left: 8px solid #333;
  transition: transform 0.3s ease;
}

.collapsible.open .collapsible-header::before {
  transform: rotate(90deg);
}

.icon {
  transition: transform 0.2s;
}

.collapsible-content {
  padding: 1rem;
  background: var(--bg);
}

/* Transition styles */
@media screen and (prefers-reduced-motion: no-preference) {
  .slide-enter-active,
  .slide-leave-active {
    transition: all 0.3s ease-out;
  }

  .slide-enter-from,
  .slide-leave-to {
    opacity: 0;
    max-height: 0;
    padding-top: 0;
    padding-bottom: 0;
  }

  .slide-enter-to,
  .slide-leave-from {
    opacity: 1;
    max-height: 100vh;
  }
}
</style>
