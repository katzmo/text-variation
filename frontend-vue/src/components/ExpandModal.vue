<template>
  <div class="expand-overlay" v-if="modelValue" @click.self="$emit('update:modelValue', null)">
    <div class="expand-modal">
      <div class="expand-modal-header">
        <span class="expand-modal-title">{{ modelValue }}</span>
        <button class="expand-modal-close" @click="$emit('update:modelValue', null)">✕</button>
      </div>
      <div class="expand-modal-body" ref="bodyEl">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps(['modelValue'])
defineEmits(['update:modelValue'])
const bodyEl = ref(null)
</script>

<style scoped>
.expand-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.expand-modal {
  background: var(--bg-panel);
  border-radius: 8px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.25);
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.expand-modal-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.expand-modal-title {
  font-family: var(--serif);
  font-size: 14px;
  font-weight: 700;
  flex: 1;
}
.expand-modal-close {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border2);
  border-radius: 4px;
  background: var(--bg);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--ink3);
}
.expand-modal-close:hover {
  background: var(--bg-hover);
  color: var(--ink);
}
.expand-modal-body {
  flex: 1;
  overflow: auto;
}
</style>
