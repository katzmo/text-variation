<template>
  <div class="panel span-2" style="min-height: 200px; max-height: 240px">
    <div class="panel-header">
      <span class="panel-title">TEXTUAL SIMILARITY NETWORK</span>
      <div
        class="panel-expand"
        style="margin-left: 4px"
        @click="$emit('expand', 'Textual similarity')"
      >
        ⤢
      </div>
      <span style="font-family: var(--mono); font-size: 9px; color: var(--ink3); margin-left: 6px">
        2D embedding
      </span>
    </div>
    <div class="panel-body" ref="containerEl" style="padding: 4px; position: relative">
      <svg ref="svgEl" style="display: block; width: 100%; height: 100%"></svg>
      <div class="map-tooltip" ref="tooltipEl"></div>
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
const tooltipEl = ref(null)

function computeMDS(wits) {
  const n = wits.length
  if (n < 2) return wits.map(() => [0, 0])
  const dist = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => {
      if (i === j) return 0
      const wi = wits[i],
        wj = wits[j]
      let d = 0
      d += wi.affiliation !== wj.affiliation ? 0.4 : 0
      d += wi.source !== wj.source ? 0.35 : 0
      d += (Math.abs(wi.year - wj.year) / 700) * 0.25
      return Math.min(d, 1)
    }),
  )
  const sq = dist.map((row) => row.map((v) => v * v))
  const rowMean = sq.map((row) => row.reduce((a, b) => a + b, 0) / n)
  const grand = rowMean.reduce((a, b) => a + b, 0) / n
  const B = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => -0.5 * (sq[i][j] - rowMean[i] - rowMean[j] + grand)),
  )
  function powerIter(M, iters = 80) {
    let v = Array.from({ length: n }, () => Math.random() - 0.5)
    for (let it = 0; it < iters; it++) {
      const mv = M.map((row) => row.reduce((s, val, k) => s + val * v[k], 0))
      const norm = Math.sqrt(mv.reduce((s, x) => s + x * x, 0)) || 1
      v = mv.map((x) => x / norm)
    }
    const lam = v.reduce((s, vi, i) => s + vi * B[i].reduce((ss, bv, k) => ss + bv * v[k], 0), 0)
    return { v, lam }
  }
  const { v: v1, lam: lam1 } = powerIter(B)
  const B2 = B.map((row, i) => row.map((val, j) => val - lam1 * v1[i] * v1[j]))
  const { v: v2, lam: lam2 } = powerIter(B2)
  return v1.map((_, i) => [v1[i] * Math.sqrt(Math.abs(lam1)), v2[i] * Math.sqrt(Math.abs(lam2))])
}

function draw() {
  const el = containerEl.value
  const svg = svgEl.value
  if (!el || !svg) return
  const W = el.clientWidth || 400
  const H = el.clientHeight || 190
  const margin = { top: 12, right: 12, bottom: 12, left: 12 }
  const iW = W - margin.left - margin.right
  const iH = H - margin.top - margin.bottom
  const wits = witnesses.value
  const coords = computeMDS(wits)
  const xs = coords.map((c) => c[0])
  const ys = coords.map((c) => c[1])
  const xScale = d3
    .scaleLinear()
    .domain([d3.min(xs), d3.max(xs)])
    .range([0, iW])
    .nice()
  const yScale = d3
    .scaleLinear()
    .domain([d3.min(ys), d3.max(ys)])
    .range([iH, 0])
    .nice()
  const s = d3.select(svg).attr('width', W).attr('height', H)
  s.selectAll('*').remove()
  const g = s.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  const n = wits.length
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++) {
      if (wits[i].source === wits[j].source && wits[i].affiliation === wits[j].affiliation)
        g.append('line')
          .attr('x1', xScale(coords[i][0]))
          .attr('y1', yScale(coords[i][1]))
          .attr('x2', xScale(coords[j][0]))
          .attr('y2', yScale(coords[j][1]))
          .attr('stroke', 'var(--border2)')
          .attr('stroke-width', 0.8)
          .attr('opacity', 0.5)
    }
  wits.forEach((w, i) => {
    const cx = xScale(coords[i][0])
    const cy = yScale(coords[i][1])
    const isSel = w.id === selectedWit.value
    const dg = g
      .append('g')
      .attr('transform', `translate(${cx},${cy})`)
      .style('cursor', 'pointer')
      .on('mouseenter', () => {
        const tip = tooltipEl.value
        if (!tip) return
        tip.textContent = `${w.id} — ${w.name}`
        tip.style.left = margin.left + cx + 8 + 'px'
        tip.style.top = margin.top + cy - 14 + 'px'
        tip.classList.add('show')
      })
      .on('mouseleave', () => tooltipEl.value?.classList.remove('show'))
      .on('click', () => {
        selectedWit.value = w.id
      })
    dg.append('circle')
      .attr('r', isSel ? 6 : 4)
      .attr('fill', isSel ? 'var(--ink)' : '#aaa8a0')
      .attr('stroke', '#fff')
      .attr('stroke-width', isSel ? 1.5 : 1)
    dg.append('text')
      .attr('x', isSel ? 8 : 6)
      .attr('y', 3.5)
      .attr('font-family', 'var(--mono)')
      .attr('font-size', isSel ? 9 : 8)
      .attr('font-weight', isSel ? 600 : 400)
      .attr('fill', isSel ? 'var(--ink)' : 'var(--ink2)')
      .text(w.id)
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
