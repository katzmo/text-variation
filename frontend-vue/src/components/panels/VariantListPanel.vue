<template>
  <div class="panel variant-list-panel">
    <div class="panel-header">
      <span class="panel-title">ACTIVE VARIANT LEXICON</span>
      <div style="display: flex; align-items: center; gap: 4px">
        <button class="vl-sort-btn" @click="sortVariants">↑↓</button>
        <div class="panel-expand" @click="$emit('expand', 'Variant list')">⤢</div>
      </div>
    </div>
    <div class="variant-list-controls">
      <span class="vl-count">{{ variants.length.toLocaleString() }} variants</span>
    </div>
    <div class="variant-list">
      <div
        v-for="(v, i) in variants"
        :key="v"
        class="variant-item"
        :class="{ selected: selectedVariant === v }"
        @click="$emit('pick', v)"
      >
        <span class="vi-num">{{ i + 1 }}.</span>
        <span class="vi-word">{{ v }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useStore } from '../../composables/useStore.js'
defineEmits(['expand', 'pick'])
const { variants, selectedVariant } = useStore()
function sortVariants() {
  variants.value = [...variants.value].sort((a, b) => a.localeCompare(b))
}
</script>

<style scoped>
.variant-list-panel {
  grid-column: 3;
  grid-row: 2 / 6;
  display: flex;
  flex-direction: column;
  max-height: 720px;
}
.variant-list-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.vl-sort-btn {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0 2px;
}
.vl-count {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
}
.variant-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.variant-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  cursor: pointer;
  transition: background 0.08s;
  font-size: 12px;
}
.variant-item:hover {
  background: var(--bg-hover);
}
.variant-item.selected {
  background: var(--sel-bg);
  color: var(--sel-fg);
}
.vi-num {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  min-width: 22px;
  text-align: right;
}
.variant-item.selected .vi-num {
  color: rgba(255, 255, 255, 0.5);
}
.vi-word {
  font-size: 12px;
}
</style>
