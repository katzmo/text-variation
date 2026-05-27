<template>
  <div class="panel span-2" style="min-height: 200px; max-height: 240px">
    <div class="panel-header">
      <span class="panel-title">VARIANT FREQUENCY DISTRIBUTION</span>
      <div style="display: flex; align-items: center; gap: 8px; margin-left: auto">
        <span
          style="
            display: flex;
            align-items: center;
            gap: 4px;
            font-family: var(--mono);
            font-size: 9px;
            color: var(--ink3);
          "
        >
          <span
            style="
              width: 10px;
              height: 10px;
              background: #555;
              display: inline-block;
              border-radius: 1px;
            "
          ></span>
          100% of selected
        </span>
        <div class="panel-expand" @click="$emit('expand', 'Variant frequency')">⤢</div>
      </div>
    </div>
    <div class="panel-body" ref="containerEl" style="padding: 6px 10px 4px">
      <svg ref="svgEl" style="display: block; width: 100%; height: 100%"></svg>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { useStore } from '../../composables/useStore.js'

defineEmits(['expand'])
const { witnesses, selectedWit } = useStore()
const containerEl = ref(null)
const svgEl = ref(null)

function draw() {
  const el = containerEl.value
  const svg = svgEl.value
  if (!el || !svg) return
  const W = el.clientWidth || 400
  const H = el.clientHeight || 180
  const margin = { top: 8, right: 16, bottom: 28, left: 44 }
  const iW = W - margin.left - margin.right
  const iH = H - margin.top - margin.bottom
  const wits = witnesses.value
  const selId = selectedWit.value
  const n = wits.length
  const bins = 10
  const allCounts = Array.from({ length: bins }).fill(0)
  const selCounts = Array.from({ length: bins }).fill(0)
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++) {
      const wi = wits[i],
        wj = wits[j]
      let sim = 1
      if (wi.affiliation !== wj.affiliation) sim -= 0.35
      if (wi.source !== wj.source) sim -= 0.3
      sim -= (Math.abs(wi.year - wj.year) / 700) * 0.35
      sim = Math.max(0, Math.min(1, sim))
      const bin = Math.min(bins - 1, Math.floor(sim * bins))
      allCounts[bin]++
      if (wi.id === selId || wj.id === selId) selCounts[bin]++
    }
  const xScale = d3.scaleLinear().domain([0, bins]).range([0, iW])
  const yScale = d3
    .scaleLinear()
    .domain([0, d3.max(allCounts) || 1])
    .range([iH, 0])
    .nice()
  const barW = iW / bins - 1
  const s = d3.select(svg).attr('width', W).attr('height', H)
  s.selectAll('*').remove()
  const g = s.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
  yScale
    .ticks(4)
    .forEach((v) =>
      g
        .append('line')
        .attr('x1', 0)
        .attr('y1', yScale(v))
        .attr('x2', iW)
        .attr('y2', yScale(v))
        .attr('stroke', 'var(--border)')
        .attr('stroke-width', 1),
    )
  allCounts.forEach((count, i) => {
    if (!count) return
    g.append('rect')
      .attr('x', xScale(i) + 0.5)
      .attr('y', yScale(count))
      .attr('width', barW)
      .attr('height', iH - yScale(count))
      .attr('fill', '#ccc4b4')
      .attr('rx', 1)
  })
  selCounts.forEach((count, i) => {
    if (!count) return
    g.append('rect')
      .attr('x', xScale(i) + 0.5)
      .attr('y', yScale(count))
      .attr('width', barW)
      .attr('height', iH - yScale(count))
      .attr('fill', '#555')
      .attr('rx', 1)
  })
  g.append('line')
    .attr('x1', 0)
    .attr('y1', iH)
    .attr('x2', iW)
    .attr('y2', iH)
    .attr('stroke', 'var(--border2)')
    .attr('stroke-width', 1)
  for (let i = 0; i <= bins; i++)
    g.append('text')
      .attr('x', xScale(i))
      .attr('y', iH + 14)
      .attr('text-anchor', 'middle')
      .attr('font-family', 'var(--mono)')
      .attr('font-size', 8)
      .attr('fill', 'var(--ink3)')
      .text(`${i * 10}%`)
  g.append('line')
    .attr('x1', 0)
    .attr('y1', 0)
    .attr('x2', 0)
    .attr('y2', iH)
    .attr('stroke', 'var(--border2)')
    .attr('stroke-width', 1)
  yScale.ticks(4).forEach((v) =>
    g
      .append('text')
      .attr('x', -5)
      .attr('y', yScale(v) + 3)
      .attr('text-anchor', 'end')
      .attr('font-family', 'var(--mono)')
      .attr('font-size', 8)
      .attr('fill', 'var(--ink3)')
      .text(v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v),
  )
  g.append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -iH / 2)
    .attr('y', -32)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'var(--sans)')
    .attr('font-size', 9)
    .attr('fill', 'var(--ink3)')
    .text('number of variants')
}

onMounted(() => {
  draw()
  window.addEventListener('resize', draw)
})
onUnmounted(() => window.removeEventListener('resize', draw))
watch([selectedWit, witnesses], () => draw(), { deep: true })
defineExpose({ draw })
</script>
