<template>
  <div>
    <div class="collation-resize" @mousedown="startResize"></div>
    <div class="collation-panel" :style="{ height: panelH + 'px' }">

      <!-- Header -->
      <div class="collation-header">
        <span class="collation-title">Collation view</span>
        <span class="collation-sub">drag columns · click segment · zoom</span>
        <div style="display:flex;align-items:center;gap:8px;margin-left:auto;">
          <span style="font-family:var(--mono);font-size:10px;color:var(--ink3);">zoom</span>
          <input type="range" min="36" max="130" v-model.number="zoom" style="width:80px;height:3px;accent-color:var(--ink)"/>
          <button class="col-settings-btn" @click="showSettings=!showSettings" title="Settings">⚙</button>
        </div>
      </div>

      <!-- Settings overlay -->
      <CollationSettings v-if="showSettings" :settings="settings" :colOrder="colOrder" @close="showSettings=false" />

      <!-- Minimap -->
      <div class="col-minimap" ref="minimapEl" @click="minimapClick">
        <div class="col-minimap-inner">
          <div class="col-minimap-col" v-for="w in colOrder" :key="w.id">
            <div v-for="(s,si) in segs" :key="si" class="col-minimap-seg" :style="{background: segColor(w.id,si)}"></div>
          </div>
        </div>
        <div class="col-minimap-vp" :style="minimapVP"></div>
      </div>

      <div class="collation-body">
        <!-- Dendro -->
        <div class="col-dendro-wrap">
          <svg ref="dendroSvg" style="display:block;"></svg>
        </div>

        <!-- Columns scroll -->
        <div class="col-scroll" ref="scrollEl" @scroll="onScroll">
          <div class="col-inner">
            <div class="col-row" ref="rowEl">
              <div
                v-for="(w, wi) in colOrder" :key="w.id"
                class="col-wit"
                :class="{ dragging: dragId===w.id, 'col-drag-over': dragOver===w.id, 'col-zoomed': zoom>90 }"
                :style="{ width: cw + 'px' }"
                draggable="true"
                @dragstart="dragId=w.id"
                @dragover.prevent="dragOver=w.id"
                @drop="onDrop(w.id)"
                @dragend="dragId=null; dragOver=null; drawDendro()"
              >
                <div class="col-badge" :class="[badgeClass(wi, w.id), { active: selectedWit===w.id }]" @click="selectedWit=w.id">
                  {{ w.id }}
                </div>
                <div class="col-segs">
                  <div
                    v-for="(s,si) in segs" :key="si"
                    class="col-seg"
                    :class="{ active: activeSeg===si, highlighted: isHighlighted(w.id,si) }"
                    :style="{ height: sh+'px', width:(cw-8)+'px', background: segColor(w.id,si) }"
                    @click="pickSeg(si)"
                  >
                    <div class="col-seg-text">{{ getSegText(w.id, si) }}</div>
                  </div>
                </div>
              </div>
              <svg class="col-wave-svg" :width="totalW" :height="totalH" style="position:absolute;top:0;left:0;pointer-events:none;">
                <path v-if="wavePath" :d="wavePath" fill="none" stroke="var(--ink)" stroke-width="1.8" stroke-linecap="round" opacity="0.7"/>
              </svg>
            </div>
          </div>
        </div>

        <!-- Detail strip -->
        <div class="col-detail" v-if="activeSeg !== null">
          <div class="col-detail-toggle" @click="detOpen=!detOpen">{{ detOpen ? '▼' : '▲' }}</div>
          <div class="col-detail-body" v-if="detOpen">
            <div class="col-detail-texts">
              <div class="col-detail-wit" v-for="(w,wi) in colOrder" :key="w.id">
                <div class="col-detail-badge" :class="badgeClass(wi, w.id)">{{ w.id }}</div>
                <div class="col-detail-name">{{ w.name }}</div>
                <div class="col-detail-segs">
                  <div v-for="(s,si) in segs" :key="si" class="col-detail-seg" :class="{ active: activeSeg===si }" @click="pickSeg(si)">
                    {{ getSegText(w.id, si) }}
                  </div>
                </div>
              </div>
            </div>
            <!-- Variant graph -->
            <div class="vg-strip">
              <div class="vg-strip-title">Variant graph</div>
              <div class="vg-strip-scroll">
                <svg ref="variantGraphSvg" style="display:block;"></svg>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import * as d3 from 'd3'
import CollationSettings from './CollationSettings.vue'
import { useStore } from '../../composables/useStore.js'
import { jaccard, upgma, leafOrder, normalizeText, badgeClass as _badgeClass } from '../../utils.js'
import { postCollate } from '../../api.js'

const { witnesses, selectedWit, selectedVariant, getSegText: storeGetSegText } = useStore()

// Expose to template
function getSegText(id, si) { return storeGetSegText(id, si) }

// ── Local state ──────────────────────────────────────────────────────────────
const panelH   = ref(340)
const zoom     = ref(58)
const colOrder = ref([])
const tree     = ref(null)
const segs     = ref(Array.from({ length: 8 }, (_, i) => `seg-${String(i+1).padStart(3,'0')}`))
const activeSeg= ref(null)
const detOpen  = ref(true)
const dragId   = ref(null)
const dragOver = ref(null)
const wavePath = ref(null)
const sx       = ref(0); const sy = ref(0)
const showSettings = ref(false)
const settings = ref({ ref: '', colorMode: 'similarity', variation: ['spelling','grammar','other'], sortBy: 'manual' })

// ── DOM refs ─────────────────────────────────────────────────────────────────
const dendroSvg      = ref(null)
const scrollEl       = ref(null)
const rowEl          = ref(null)
const minimapEl      = ref(null)
const variantGraphSvg= ref(null)

// ── Computed ─────────────────────────────────────────────────────────────────
const cw     = computed(() => Math.max(30, Math.round(zoom.value * 0.68)))
const sh     = computed(() => Math.max(7,  Math.round(zoom.value * 0.175)))
const BADGE_H = 38
const totalW = computed(() => colOrder.value.length * cw.value + 16)
const totalH = computed(() => BADGE_H + segs.value.length * (sh.value + 2) + 10)

function badgeClass(wi, id) { return _badgeClass(wi, id) }

function normText(t) { return normalizeText(t, settings.value.variation) }

function simScore(id, si) {
  const t = normText(getSegText(id, si))
  if (!t) return 0
  const ref = settings.value.ref
  if (ref && ref !== id) {
    const rt = normText(getSegText(ref, si))
    return rt ? jaccard(t, rt) : 0
  }
  const others = colOrder.value.filter(w => w.id !== id)
  if (!others.length) return 1
  return others.reduce((s, w) => s + jaccard(t, normText(getSegText(w.id, si))), 0) / others.length
}

function segColor(id, si) {
  const score = simScore(id, si)
  if (settings.value.colorMode === 'position' && settings.value.ref) {
    return `hsl(${(si / segs.value.length) * 280},45%,${55 + score * 25}%)`
  }
  return `hsl(0,0%,${50 + score * 38}%)`
}

function isHighlighted(id, si) {
  if (!selectedVariant.value) return false
  return getSegText(id, si).toLowerCase().includes(selectedVariant.value.toLowerCase())
}

const minimapVP = computed(() => {
  if (!scrollEl.value) return {}
  const el = scrollEl.value; const mw = 116, mh = 68
  return {
    left: (sx.value / (el.scrollWidth || 1) * mw) + 'px',
    top:  (sy.value / (el.scrollHeight || 1) * mh) + 'px',
    width: ((el.clientWidth || 1) / (el.scrollWidth || 1) * mw) + 'px',
    height: ((el.clientHeight || 1) / (el.scrollHeight || 1) * mh) + 'px',
  }
})

function onScroll(e) { sx.value = e.target.scrollLeft; sy.value = e.target.scrollTop }

function minimapClick(e) {
  if (!scrollEl.value || !minimapEl.value) return
  const r = minimapEl.value.getBoundingClientRect()
  scrollEl.value.scrollLeft = (e.clientX - r.left) / r.width * scrollEl.value.scrollWidth
  scrollEl.value.scrollTop  = (e.clientY - r.top)  / r.height * scrollEl.value.scrollHeight
}

function onDrop(toId) {
  if (!dragId.value || dragId.value === toId) return
  const arr = [...colOrder.value]
  const fi = arr.findIndex(w => w.id === dragId.value)
  const ti = arr.findIndex(w => w.id === toId)
  const [m] = arr.splice(fi, 1); arr.splice(ti, 0, m)
  colOrder.value = arr
}

// ── Dendro ───────────────────────────────────────────────────────────────────
function drawDendro() {
  if (!dendroSvg.value || !tree.value) return
  const cols = colOrder.value; const n = cols.length
  const W = n * cw.value + 16; const H = 100
  const svg = d3.select(dendroSvg.value).attr('width', W).attr('height', H)
  svg.selectAll('*').remove()

  function xOf(id) { const idx = cols.findIndex(w => w.id === id); return idx < 0 ? -999 : 8 + idx * cw.value + cw.value / 2 }
  function leafIds(node) { if (!node.left && !node.right) return [node.id]; return [...leafIds(node.left), ...leafIds(node.right)] }
  function midX(node) { const xs = leafIds(node).map(id => xOf(id)).filter(x => x > 0); if (!xs.length) return 0; return (Math.min(...xs) + Math.max(...xs)) / 2 }
  function nodeY(node) { return H - 8 - node.h * (H - 40) * 4.5 }
  function draw(node) {
    if (!node.left && !node.right) return
    const ny = nodeY(node); const lx = midX(node.left); const rx = midX(node.right)
    const ly = node.left.left ? nodeY(node.left) : H - 8; const ry = node.right.left ? nodeY(node.right) : H - 8
    const g = svg.append('g')
    g.append('line').attr('x1',lx).attr('y1',ny).attr('x2',rx).attr('y2',ny).attr('stroke','#aaa').attr('stroke-width',1.5)
    g.append('line').attr('x1',lx).attr('y1',ny).attr('x2',lx).attr('y2',ly).attr('stroke','#aaa').attr('stroke-width',1.5)
    g.append('line').attr('x1',rx).attr('y1',ny).attr('x2',rx).attr('y2',ry).attr('stroke','#aaa').attr('stroke-width',1.5)
    draw(node.left); draw(node.right)
  }
  draw(tree.value)
}

// ── Wave ─────────────────────────────────────────────────────────────────────
function drawWave() {
  const si = activeSeg.value; if (si === null) return
  const cols = colOrder.value
  const segY = BADGE_H + si * (sh.value + 2) + sh.value / 2
  const amp  = Math.max(8, Math.min(30, sh.value * 1.2))
  const pts  = cols.map((w, i) => [8 + i * cw.value + cw.value / 2, segY + (1 - simScore(w.id, si)) * amp])
  if (pts.length < 2) { wavePath.value = null; return }
  wavePath.value = d3.line().x(d => d[0]).y(d => d[1]).curve(d3.curveCatmullRom.alpha(0.5))(pts)
}

// ── Variant graph ─────────────────────────────────────────────────────────────
async function pickSeg(si) {
  activeSeg.value = si
  drawWave()
  const segId = segs.value[si]; if (!segId) return
  let data = null
  // Skip backend call for mock segment IDs (no real witnesses uploaded yet)
  const isMockSegment = /^seg-\d+$/.test(segId)
  if (!isMockSegment) {
    try { data = await postCollate(segId, colOrder.value.map(w => w.id)) } catch(e) { /* fall through */ }
  }
  if (!data) data = mockCollate(si)
  if (variantGraphSvg.value) drawVariantGraph(variantGraphSvg.value, data)
}

function mockCollate(si) {
  const wits = colOrder.value
  const tokens = wits.map(w => ({ id: w.id, words: getSegText(w.id, si).split(/\s+/).filter(Boolean) }))
  const maxLen = Math.max(...tokens.map(t => t.words.length), 1)
  const table = []
  for (let i = 0; i < maxLen; i++) {
    const row = {}
    tokens.forEach(t => { const w = t.words[i] || ''; row[t.id] = w ? [{ t: w, n: w.toLowerCase() }] : [{ t: '', n: '' }] })
    table.push(row)
  }
  return { table, witnesses: tokens.map(t => t.id) }
}

function drawVariantGraph(svgEl, data) {
  if (!svgEl || !data?.table) return
  const table = data.table; const wits = data.witnesses
  const nodes = []; const links = []; const prevNode = {}
  table.forEach((row, colIdx) => {
    const groups = {}
    wits.forEach(wit => {
      const tok = row[wit]; const text = tok?.[0]?.t || ''; const key = text.toLowerCase() || '__gap__'
      if (!groups[key]) groups[key] = { id: `c${colIdx}_${key}`, text: text || '—', isGap: !text, colIdx, witnesses: [] }
      groups[key].witnesses.push(wit)
    })
    Object.values(groups).forEach((node, i) => { node.yOffset = (i - (Object.values(groups).length - 1) / 2) * 32; nodes.push(node) })
    wits.forEach(wit => {
      const text = row[wit]?.[0]?.t || ''; const key = text.toLowerCase() || '__gap__'; const curId = `c${colIdx}_${key}`
      if (colIdx > 0 && prevNode[wit]) {
        let link = links.find(l => l.source === prevNode[wit] && l.target === curId)
        if (!link) { link = { source: prevNode[wit], target: curId, weight: 0, witnesses: [] }; links.push(link) }
        link.weight++; link.witnesses.push(wit)
      }
      prevNode[wit] = curId
    })
  })

  const colSpacing = 90; const nodeW = 64
  const W = Math.max(600, table.length * colSpacing + 80); const H = 180
  nodes.forEach(n => { n.x = n.colIdx * colSpacing; n.y = n.yOffset })
  const linkData = links.map(l => ({ ...l, sn: nodes.find(n => n.id === l.source), tn: nodes.find(n => n.id === l.target) })).filter(l => l.sn && l.tn)
  const selVar = (selectedVariant.value || '').toLowerCase()

  const svg = d3.select(svgEl).attr('width', W).attr('height', H)
  svg.selectAll('*').remove()
  const g = svg.append('g').attr('transform', `translate(40,${H/2})`)
  g.selectAll('.vg-link').data(linkData).join('path').attr('class','vg-link')
    .attr('d', d => `M${d.sn.x} ${d.sn.y} C${d.sn.x+colSpacing/2.5} ${d.sn.y},${d.tn.x-colSpacing/2.5} ${d.tn.y},${d.tn.x} ${d.tn.y}`)
    .attr('fill','none').attr('stroke','#bbb4a4').attr('stroke-width', d => Math.max(1, Math.min(8, d.weight * 1.4))).attr('opacity',0.55)
    .append('title').text(d => `${d.witnesses.join(', ')} (${d.weight})`)
  const ng = g.selectAll('.vg-node').data(nodes).join('g').attr('class','vg-node').attr('transform', d => `translate(${d.x},${d.y})`)
  ng.append('rect').attr('x',-nodeW/2).attr('y',-11).attr('width',nodeW).attr('height',22).attr('rx',11)
    .attr('fill', d => selVar && d.text.toLowerCase().includes(selVar) ? '#f0d090' : d.isGap ? '#f0ede6' : '#fff')
    .attr('stroke', d => selVar && d.text.toLowerCase().includes(selVar) ? '#c8860a' : '#ccc4b4')
    .attr('stroke-width', d => selVar && d.text.toLowerCase().includes(selVar) ? 2 : 1)
  ng.append('text').attr('text-anchor','middle').attr('dominant-baseline','middle').attr('font-family','var(--mono)').attr('font-size',10).attr('fill', d => d.isGap ? '#9a9088' : '#1c1a17').attr('font-style', d => d.isGap ? 'italic' : 'normal').text(d => d.text.length > 9 ? d.text.slice(0,8)+'…' : d.text)
  ng.append('title').text(d => `${d.text}\n→ ${d.witnesses.join(', ')}`)
}

// ── Resize ───────────────────────────────────────────────────────────────────
function startResize(e) {
  e.preventDefault()
  const startY = e.clientY; const startH = panelH.value
  const onMove = ev => { panelH.value = Math.max(180, Math.min(700, startH + (startY - ev.clientY))) }
  const onUp   = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); drawDendro() }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}

// ── Sort ─────────────────────────────────────────────────────────────────────
function getStemmaDistance(id, refId) {
  function findPath(node, target, path = []) {
    if (!node) return null
    if (!node.left && !node.right) return node.id === target ? path : null
    return findPath(node.left, target, [...path, 'L']) || findPath(node.right, target, [...path, 'R'])
  }
  const p1 = findPath(tree.value, id) || []; const p2 = findPath(tree.value, refId) || []
  let common = 0; while (common < p1.length && common < p2.length && p1[common] === p2[common]) common++
  return (p1.length - common) + (p2.length - common)
}

function applySort(mode) {
  const all = [...colOrder.value]
  const wit = id => witnesses.value.find(w => w.id === id) || all.find(w => w.id === id)
  switch (mode) {
    case 'time':         colOrder.value = all.sort((a,b) => (wit(a.id)?.year||0) - (wit(b.id)?.year||0)); break
    case 'category':     colOrder.value = all.sort((a,b) => { const af=(wit(a.id)?.affiliation||'').localeCompare(wit(b.id)?.affiliation||''); return af||((wit(a.id)?.source||'').localeCompare(wit(b.id)?.source||'')); }); break
    case 'alphabetical': colOrder.value = all.sort((a,b) => a.id.localeCompare(b.id)); break
    case 'similarity':   colOrder.value = all.sort((a,b) => segs.value.reduce((s,_,si)=>s+simScore(b.id,si),0) - segs.value.reduce((s,_,si)=>s+simScore(a.id,si),0)); break
    case 'relationships': {
      const ref = settings.value.ref
      if (ref) colOrder.value = all.sort((a,b) => getStemmaDistance(a.id,ref) - getStemmaDistance(b.id,ref))
      else { const o = leafOrder(tree.value); colOrder.value = o.map(id => wit(id)).filter(Boolean) }
      break
    }
    default: { const o = leafOrder(tree.value); colOrder.value = o.map(id => wit(id)).filter(Boolean) }
  }
  drawDendro()
}

// ── Watchers ─────────────────────────────────────────────────────────────────
watch([zoom, colOrder], () => { drawDendro(); if (activeSeg.value !== null) drawWave() })
watch(activeSeg, () => drawWave())
watch(selectedVariant, () => { if (activeSeg.value !== null) { const data = mockCollate(activeSeg.value); if (variantGraphSvg.value) drawVariantGraph(variantGraphSvg.value, data) } })
watch(() => settings.value.sortBy, mode => applySort(mode))
watch(() => [...settings.value.variation, settings.value.colorMode, settings.value.ref], () => { if (activeSeg.value !== null) drawWave() }, { deep: true })
watch(witnesses, () => {
  const ids = witnesses.value.map(w => w.id)
  tree.value = upgma(ids, storeGetSegText)
  const order = leafOrder(tree.value)
  colOrder.value = order.map(id => witnesses.value.find(w => w.id === id)).filter(Boolean)
  drawDendro()
}, { deep: true })

// ── Mount ────────────────────────────────────────────────────────────────────
onMounted(() => {
  const ids = witnesses.value.map(w => w.id)
  tree.value = upgma(ids, storeGetSegText)
  const order = leafOrder(tree.value)
  colOrder.value = order.map(id => witnesses.value.find(w => w.id === id)).filter(Boolean)
  setTimeout(drawDendro, 50)
})

// Expose so parent (App) can update segs after upload
defineExpose({ segs, colOrder, tree })
</script>

<style scoped>
.collation-resize { height:6px;background:var(--border);cursor:ns-resize;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:background .1s; }
.collation-resize:hover { background:var(--border2); }
.collation-resize::before { content:'';width:32px;height:2px;background:var(--ink3);border-radius:2px; }
.collation-panel { flex-shrink:0;background:var(--bg-panel);border-top:2px solid var(--border2);display:flex;flex-direction:column;position:relative;min-height:180px; }
.collation-header { display:flex;align-items:center;gap:10px;padding:6px 12px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--bg-panel); }
.collation-title { font-family:var(--serif);font-size:12px;font-weight:700; }
.collation-sub { font-family:var(--mono);font-size:9px;color:var(--ink3); }
.col-settings-btn { width:26px;height:26px;border:1px solid var(--border2);border-radius:4px;background:var(--bg);cursor:pointer;font-size:13px;color:var(--ink2);display:flex;align-items:center;justify-content:center;transition:background .1s; }
.col-settings-btn:hover { background:var(--bg-hover);color:var(--ink); }
.col-minimap { position:absolute;top:32px;left:8px;width:120px;background:var(--bg-panel);border:1px solid var(--border2);z-index:50;cursor:crosshair; }
.col-minimap-inner { display:flex;height:70px;gap:1px;padding:2px; }
.col-minimap-col { display:flex;flex-direction:column;gap:1px;flex:1; }
.col-minimap-seg { flex:1; }
.col-minimap-vp { position:absolute;border:2px solid var(--ink);background:rgba(0,0,0,0.06);pointer-events:none;top:0;left:0; }
.collation-body { flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative; }
.col-dendro-wrap { position:sticky;top:0;z-index:10;background:var(--bg);flex-shrink:0;padding-top:4px; }
.col-scroll { flex:1;overflow:auto; }
.col-inner { min-height:100%;padding:0 4px 8px; }
.col-row { display:flex;align-items:flex-start;position:relative; }
.col-wit { display:flex;flex-direction:column;align-items:center;flex-shrink:0;cursor:grab;position:relative;transition:opacity .12s; }
.col-wit.dragging { opacity:.4;cursor:grabbing; }
.col-wit.col-drag-over::before { content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--ink);z-index:10; }
.col-badge { width:34px;height:34px;border-radius:50%;background:#e4e4e4;border:1.5px solid #bbb;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:700;color:#333;cursor:pointer;flex-shrink:0;transition:background .1s; }
.col-badge.active { background:var(--ink);color:#fff;border-color:var(--ink); }
.col-badge.cb0 { background:#e4e4e4; } .col-badge.cb1 { background:#f4c4b4;border-color:#e09880; } .col-badge.cb2 { background:#bce0b8;border-color:#88c480; } .col-badge.cb3 { background:#b4cce8;border-color:#80a8d4; } .col-badge.cb4 { background:#f0e4a4;border-color:#d4c464; } .col-badge.cb5 { background:#d4bce0;border-color:#b490cc; }
.col-segs { display:flex;flex-direction:column;gap:2px;padding:2px 3px;width:100%; }
.col-seg { border-radius:2px;cursor:pointer;overflow:hidden;position:relative;transition:filter .08s; }
.col-seg:hover { filter:brightness(1.1); }
.col-seg.active { outline:2px solid var(--ink);outline-offset:-1px; }
.col-seg.highlighted { outline:2px solid #c8860a !important;outline-offset:-1px; }
.col-seg-text { font-size:6px;line-height:1.3;color:#111;padding:2px 3px;overflow:hidden;display:none;width:100%; }
.col-zoomed .col-seg-text { display:block; }
.col-wave-svg { position:absolute;top:0;left:0;pointer-events:none;z-index:20; }
.col-detail { flex-shrink:0;background:var(--bg-panel);border-top:1px solid var(--border); }
.col-detail-toggle { display:flex;align-items:center;justify-content:center;height:20px;cursor:pointer;color:var(--ink3);font-size:10px;background:var(--bg);border-bottom:1px solid var(--border); }
.col-detail-toggle:hover { background:var(--bg-hover); }
.col-detail-body { max-height:300px;overflow-y:auto; }
.col-detail-texts { display:flex;overflow-x:auto;padding:6px 8px;gap:0; }
.col-detail-wit { min-width:140px;max-width:180px;flex-shrink:0;padding:0 8px;border-right:1px solid var(--border); }
.col-detail-wit:last-child { border-right:none; }
.col-detail-badge { width:26px;height:26px;border-radius:50%;background:#e4e4e4;border:1px solid #bbb;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:700;margin-bottom:3px; }
.col-detail-name { font-size:9px;color:var(--ink3);margin-bottom:4px; }
.col-detail-segs { display:flex;flex-direction:column;gap:2px; }
.col-detail-seg { background:var(--bg);border-radius:2px;padding:3px 5px;font-size:9px;line-height:1.4;color:var(--ink2);cursor:pointer; }
.col-detail-seg:hover { background:var(--bg-hover); }
.col-detail-seg.active { background:var(--border);border-left:2px solid var(--ink); }
.vg-strip { border-top:1px solid var(--border);padding:8px 12px;background:var(--bg); }
.vg-strip-title { font-family:var(--serif);font-size:11px;font-weight:700;margin-bottom:6px;color:var(--ink); }
.vg-strip-scroll { overflow-x:auto;padding-bottom:4px; }
</style>
