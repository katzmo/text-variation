<template>
  <div class="shell">
    <div class="header">
      <div class="header-title">Prototype D</div>
      <button class="upload-btn" @click="showUpload=true">↑ Upload texts</button>
    </div>

    <UploadModal v-if="showUpload" @close="showUpload=false" />

    <div class="body">
      <WitnessSidebar />
      <div class="main">
        <div class="dashboard">
          <TimelinePanel  @expand="expandPanel=$event" />
          <OriginMap      @expand="expandPanel=$event" />
          <BarChartPanel  title="AFFILIATION" groupBy="affiliation" @expand="expandPanel=$event" />
          <BarChartPanel  title="SOURCE"      groupBy="source"      @expand="expandPanel=$event" />
          <EmbeddingPanel @expand="expandPanel=$event" />
          <FrequencyPanel @expand="expandPanel=$event" />
          <VariantListPanel @expand="expandPanel=$event" @pick="pickVariant" />
        </div>
        <CollationView />
      </div>
    </div>

    <ExpandModal v-model="expandPanel">
      <div v-if="expandPanel==='CHRONOLOGICAL DISTRIBUTION'"     style="height:100%;padding:8px 16px;"><TimelinePanel /></div>
      <div v-if="expandPanel==='GEOGRAPHICAL ORIGIN'"            style="height:100%;position:relative;"><OriginMap /></div>
      <div v-if="expandPanel==='AFFILIATION'"                    style="height:100%;padding:8px;"><BarChartPanel title="AFFILIATION" groupBy="affiliation" /></div>
      <div v-if="expandPanel==='SOURCE'"                         style="height:100%;padding:8px;"><BarChartPanel title="SOURCE" groupBy="source" /></div>
      <div v-if="expandPanel==='TEXTUAL SIMILARITY NETWORK'"     style="height:100%;padding:4px;"><EmbeddingPanel /></div>
      <div v-if="expandPanel==='VARIANT FREQUENCY DISTRIBUTION'" style="height:100%;padding:6px 16px 4px;"><FrequencyPanel /></div>
      <div v-if="expandPanel==='ACTIVE VARIANT LEXICON'"         style="height:100%;overflow-y:auto;padding:8px 0;"><VariantListPanel @pick="pickVariant" /></div>
    </ExpandModal>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WitnessSidebar   from './components/WitnessSidebar.vue'
import UploadModal      from './components/upload/UploadModal.vue'
import ExpandModal      from './components/ExpandModal.vue'
import TimelinePanel    from './components/panels/TimelinePanel.vue'
import OriginMap        from './components/panels/OriginMap.vue'
import BarChartPanel    from './components/panels/BarChartPanel.vue'
import EmbeddingPanel   from './components/panels/EmbeddingPanel.vue'
import FrequencyPanel   from './components/panels/FrequencyPanel.vue'
import VariantListPanel from './components/panels/VariantListPanel.vue'
import CollationView    from './components/collation/CollationView.vue'
import { useStore }     from './composables/useStore.js'
const { selectedVariant } = useStore()
const showUpload  = ref(false)
const expandPanel = ref(null)
function pickVariant(v) { selectedVariant.value = v }
</script>

<style scoped>
.upload-btn { position:absolute;right:12px;display:flex;align-items:center;gap:5px;padding:5px 12px;background:var(--ink);color:#fff;border:none;border-radius:4px;font-family:var(--sans);font-size:12px;font-weight:500;cursor:pointer;transition:opacity .1s; }
.upload-btn:hover { opacity:.85; }
</style>
