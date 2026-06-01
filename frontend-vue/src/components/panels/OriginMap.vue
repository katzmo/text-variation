<template>
  <div class="panel" style="min-height: 180px; max-height: 220px">
    <div class="panel-header">
      <span class="panel-title">GEOGRAPHICAL ORIGIN</span>
      <div class="panel-expand" @click="$emit('expand', 'Origin')">⤢</div>
    </div>
    <div
      class="map-body"
      ref="containerEl"
      style="padding: 0; overflow: hidden; position: relative; flex: 1"
    >
      <svg ref="svgEl" style="display: block; width: 100%; height: 100%"></svg>
      <div class="map-tooltip" ref="tooltipEl"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import { useStore } from '../../composables/useStore.js'

defineEmits(['expand'])
const { witnesses, selectedWit } = useStore()
const containerEl = ref(null)
const svgEl = ref(null)
const tooltipEl = ref(null)
let worldData = null

async function draw() {
  const el = containerEl.value
  const svg = svgEl.value
  if (!el || !svg) return
  const W = el.clientWidth || 300
  const H = el.clientHeight || 180

  if (!worldData) {
    try {
      const r = await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      worldData = await r.json()
    } catch (e) {
      worldData = null
    }
  }

  const projection = d3
    .geoNaturalEarth1()
    .scale(W / 6.5)
    .translate([W / 2, H / 2])
  const path = d3.geoPath().projection(projection)
  const s = d3.select(svg).attr('width', W).attr('height', H)
  s.selectAll('*').remove()
  s.append('rect').attr('width', W).attr('height', H).attr('fill', '#e8e4dc')

  if (worldData) {
    s.append('g')
      .selectAll('path')
      .data(topojson.feature(worldData, worldData.objects.countries).features)
      .join('path')
      .attr('d', path)
      .attr('fill', '#c8c0b0')
      .attr('stroke', '#b8b0a0')
      .attr('stroke-width', 0.4)
  }

  const grouped = d3.group(witnesses.value, (w) => `${w.origin[0]},${w.origin[1]}`)
  grouped.forEach((wits, key) => {
    const [lat, lng] = key.split(',').map(Number)
    const [px, py] = projection([lng, lat]) || [0, 0]
    const isAnySelected = wits.some((w) => w.id === selectedWit.value)
    if (wits.length > 1)
      s.append('circle')
        .attr('cx', px)
        .attr('cy', py)
        .attr('r', 5 + wits.length * 0.8)
        .attr('fill', 'none')
        .attr('stroke', isAnySelected ? 'var(--ink)' : '#888')
        .attr('stroke-width', 1)
        .attr('opacity', 0.4)

    const dg = s.append('g').attr('transform', `translate(${px},${py})`).style('cursor', 'pointer')
    dg.append('circle')
      .attr('r', isAnySelected ? 5 : 4)
      .attr('fill', isAnySelected ? 'var(--ink)' : '#666')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.2)
      .attr('opacity', isAnySelected ? 1 : 0.75)
    if (wits.length > 1)
      dg.append('text')
        .attr('dy', 3.5)
        .attr('text-anchor', 'middle')
        .attr('font-family', 'var(--mono)')
        .attr('font-size', 7)
        .attr('fill', '#fff')
        .attr('pointer-events', 'none')
        .text(wits.length)

    dg.on('mouseenter', () => {
      const tip = tooltipEl.value
      if (!tip) return
      tip.textContent = wits.map((w) => `${w.id} (${w.year})`).join(' · ')
      tip.style.left = px + 8 + 'px'
      tip.style.top = py - 14 + 'px'
      tip.classList.add('show')
    })
      .on('mouseleave', () => tooltipEl.value?.classList.remove('show'))
      .on('click', () => {
        selectedWit.value = wits[0].id
      })
  })
}

onMounted(() => {
  draw()
  window.addEventListener('resize', draw)
})
onUnmounted(() => window.removeEventListener('resize', draw))
watch([selectedWit, witnesses], () => draw(), { deep: true })
defineExpose({ draw })
</script>
