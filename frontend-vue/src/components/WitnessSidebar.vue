<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">Witnesses</span>
      <span class="sidebar-count">{{ witnesses.length }}</span>
    </div>
    <div class="sidebar-search">
      <input v-model="witSearch" placeholder="Search…" />
    </div>
    <div class="witness-list">
      <div
        v-for="w in filteredWitnesses"
        :key="w.id"
        class="witness-item"
        :class="{ selected: selectedWit === w.id }"
        @click="selectedWit = w.id"
      >
        <div class="wit-bullet"></div>
        <span class="wit-id">{{ w.id }}</span>
        <span class="wit-name">{{ w.name }}</span>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { useStore } from '../composables/useStore.js'
const { witnesses, selectedWit, witSearch, filteredWitnesses } = useStore()
</script>

<style scoped>
.sidebar {
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sidebar-title {
  font-family: var(--serif);
  font-size: 13px;
  font-weight: 700;
}
.sidebar-count {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink3);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 1px 6px;
}
.sidebar-search {
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.sidebar-search input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--border2);
  border-radius: 4px;
  font-family: var(--sans);
  font-size: 12px;
  background: var(--bg);
  color: var(--ink);
  outline: none;
}
.sidebar-search input:focus {
  border-color: var(--ink3);
}
.witness-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.witness-item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px;
  cursor: pointer;
  transition: background 0.1s;
  user-select: none;
}
.witness-item:hover {
  background: var(--bg-hover);
}
.witness-item.selected {
  background: var(--sel-bg);
  color: var(--sel-fg);
}
.wit-bullet {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ink3);
  flex-shrink: 0;
  margin-top: 1px;
}
.witness-item.selected .wit-bullet {
  background: rgba(255, 255, 255, 0.5);
}
.wit-id {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  flex-shrink: 0;
  min-width: 32px;
}
.wit-name {
  font-size: 12px;
  color: var(--ink);
  line-height: 1.3;
}
.witness-item.selected .wit-id {
  color: rgba(255, 255, 255, 0.6);
}
.witness-item.selected .wit-name {
  color: #fff;
}
</style>
