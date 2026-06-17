<template>
  <div class="shell">
    <header class="header">
      <h1 class="header-title">Prototype D</h1>
      <button class="upload-btn" @click="showUpload = true">↑ Upload texts</button>
    </header>

    <UploadModal v-if="showUpload" @close="showUpload = false" />

    <WitnessSidebar />
    <main class="main">
      <Collapsible title="Dashboard">
        <div class="dashboard">
          <TimelinePanel title="Chronological Distribution" @expand="expandPanel = $event" />
          <OriginMap title="Geographical Origin" @expand="expandPanel = $event" />
          <BarChartPanel title="Affiliation" groupBy="affiliation" @expand="expandPanel = $event" />
          <BarChartPanel title="Source" groupBy="source" @expand="expandPanel = $event" />
          <EmbeddingPanel title="Textual Similarity Network" @expand="expandPanel = $event" />
          <FrequencyPanel title="Variant Frequency Distribution" @expand="expandPanel = $event" />
          <VariantListPanel
            title="Active Variant Lexicon"
            @expand="expandPanel = $event"
            @pick="pickVariant"
          />
        </div>
      </Collapsible>
      <CollationView />
    </main>

    <ExpandModal v-model="expandPanel">
      <div v-if="expandPanel === 'Timeline'" style="height: 100%; padding: 8px 16px">
        <TimelinePanel />
      </div>
      <div v-if="expandPanel === 'Origin'" style="height: 100%; position: relative">
        <OriginMap />
      </div>
      <div v-if="expandPanel === 'Affiliation'" style="height: 100%; padding: 8px">
        <BarChartPanel title="AFFILIATION" groupBy="affiliation" />
      </div>
      <div v-if="expandPanel === 'Source'" style="height: 100%; padding: 8px">
        <BarChartPanel title="SOURCE" groupBy="source" />
      </div>
      <div v-if="expandPanel === 'Textual similarity'" style="height: 100%; padding: 4px">
        <EmbeddingPanel />
      </div>
      <div v-if="expandPanel === 'Variant frequency'" style="height: 100%; padding: 6px 16px 4px">
        <FrequencyPanel />
      </div>
      <div
        v-if="expandPanel === 'Variant list'"
        style="height: 100%; overflow-y: auto; padding: 8px 0"
      >
        <VariantListPanel @pick="pickVariant" />
      </div>
    </ExpandModal>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WitnessSidebar from './components/WitnessSidebar.vue'
import Collapsible from './components/Collapsible.vue'
import UploadModal from './components/upload/UploadModal.vue'
import ExpandModal from './components/ExpandModal.vue'
import TimelinePanel from './components/panels/TimelinePanel.vue'
import OriginMap from './components/panels/OriginMap.vue'
import BarChartPanel from './components/panels/BarChartPanel.vue'
import EmbeddingPanel from './components/panels/EmbeddingPanel.vue'
import FrequencyPanel from './components/panels/FrequencyPanel.vue'
import VariantListPanel from './components/panels/VariantListPanel.vue'
import CollationView from './components/collation/CollationView.vue'
import { useStore } from './composables/useStore.js'
const { selectedVariant } = useStore()
const showUpload = ref(false)
const expandPanel = ref(null)
function pickVariant(v) {
  selectedVariant.value = v
}
</script>

<style scoped>
.upload-btn {
  position: absolute;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: var(--ink);
  color: #fff;
  border: none;
  border-radius: 4px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.1s;
}

.upload-btn:hover {
  opacity: 0.85;
}
</style>
