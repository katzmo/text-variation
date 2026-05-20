<template>
  <div class="col-settings-overlay" @click.self="$emit('close')">
    <div class="col-settings-panel">
      <div class="col-settings-header">
        <span class="col-settings-title">Settings</span>
        <button class="col-settings-close" @click="$emit('close')">✕</button>
      </div>

      <div class="col-settings-group">
        <div class="col-settings-label">Reference text</div>
        <select class="col-settings-select" v-model="settings.ref">
          <option value="">None</option>
          <option v-for="w in colOrder" :key="w.id" :value="w.id">{{ w.name || w.id }}</option>
        </select>
      </div>

      <div class="col-settings-group">
        <div class="col-settings-label">Color</div>
        <div class="col-settings-radio">
          <label><input type="radio" v-model="settings.colorMode" value="similarity"/> Similarity value</label>
          <label :class="{ disabled: !settings.ref }">
            <input type="radio" v-model="settings.colorMode" value="position" :disabled="!settings.ref"/>
            Position in reference text
          </label>
        </div>
      </div>

      <div class="col-settings-group">
        <div class="col-settings-label">Include variation in</div>
        <div class="col-settings-check">
          <label v-for="v in varTypes" :key="v.k">
            <input type="checkbox" v-model="settings.variation" :value="v.k"/> {{ v.l }}
          </label>
        </div>
      </div>

      <div class="col-settings-group">
        <div class="col-settings-label">Sort by</div>
        <select class="col-settings-select" v-model="settings.sortBy">
          <option value="manual">Manual order (tree)</option>
          <option value="time">Time</option>
          <option value="category">Categories (affiliation)</option>
          <option value="alphabetical">Alphabetical</option>
          <option value="similarity">Similarity to reference</option>
          <option value="relationships">Relationships (tree distance)</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ settings: Object, colOrder: Array })
defineEmits(['close'])

const varTypes = [
  { k: 'punctuation', l: 'Punctuation' },
  { k: 'orthography', l: 'Orthography' },
  { k: 'spelling',    l: 'Spelling' },
  { k: 'grammar',     l: 'Grammar' },
  { k: 'other',       l: 'Other' },
]
</script>

<style scoped>
.col-settings-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.15); z-index: 250; display: flex; align-items: flex-start; justify-content: flex-end; padding: 80px 12px 0; }
.col-settings-panel { background: #fff; border-radius: 10px; padding: 18px 18px 16px; width: 250px; box-shadow: 0 4px 24px rgba(0,0,0,0.18); border: 1px solid var(--border); }
.col-settings-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.col-settings-title { font-family: var(--serif); font-size: 14px; font-weight: 700; }
.col-settings-close { border: none; background: none; cursor: pointer; font-size: 16px; color: var(--ink3); padding: 0; }
.col-settings-close:hover { color: var(--ink); }
.col-settings-group { margin-bottom: 14px; }
.col-settings-group:last-child { margin-bottom: 0; }
.col-settings-label { font-size: 12px; color: var(--ink2); margin-bottom: 6px; font-weight: 500; }
.col-settings-select { width: 100%; padding: 6px 9px; border: 1px solid var(--border2); border-radius: 6px; font-size: 12px; background: var(--bg); color: var(--ink); cursor: pointer; font-family: var(--sans); }
.col-settings-radio, .col-settings-check { display: flex; flex-direction: column; gap: 7px; }
.col-settings-radio label, .col-settings-check label { display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer; color: var(--ink); }
.col-settings-radio label.disabled { color: var(--ink3); cursor: default; }
.col-settings-radio input, .col-settings-check input { accent-color: var(--ink); }
</style>
