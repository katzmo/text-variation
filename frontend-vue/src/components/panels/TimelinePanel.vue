<template>
  <div class="panel span-full" style="min-height:100px;max-height:110px;">
    <div class="panel-header">
      <span class="panel-title">CHRONOLOGICAL DISTRIBUTION</span>
      <div class="panel-expand" @click="$emit('expand', 'Timeline')">⤢</div>
    </div>
    <div class="timeline-body" ref="containerEl" style="flex:1;position:relative;overflow:hidden;padding:2px 10px 4px;">
      <svg ref="svgEl" style="display:block;width:100%;"></svg>
      <div class="tl-tooltip" ref="tooltipEl"></div>
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
const svgEl       = ref(null)
const tooltipEl   = ref(null)

function draw() {
  const el  = containerEl.value
  const svg = svgEl.value
  if (!el || !svg) return
  const W = el.clientWidth || 600
  const H = 46
  const margin = { left: 8, right: 8, top: 6, bottom: 18 }
  const iW = W - margin.left - margin.right

  const years = witnesses.value.map(w => w.year)
  const xScale = d3.scaleLinear()
    .domain([Math.floor(Math.min(...years) / 100) * 100, Math.ceil(Math.max(...years) / 100) * 100])
    .range([0, iW])

  const s = d3.select(svg).attr('width', W).attr('height', H)
  s.selectAll('*').remove()
  const g = s.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  const axisY = H - margin.bottom - margin.top
  g.append('line').attr('x1',0).attr('y1',axisY).attr('x2',iW).attr('y2',axisY).attr('stroke','var(--border2)').attr('stroke-width',1)

  d3.range(xScale.domain()[0], xScale.domain()[1]+1, 100).forEach(y => {
    const x = xScale(y)
    g.append('line').attr('x1',x).attr('y1',axisY).attr('x2',x).attr('y2',axisY+4).attr('stroke','var(--border2)').attr('stroke-width',1)
    g.append('text').attr('x',x).attr('y',axisY+13).attr('text-anchor','middle').attr('font-family','var(--mono)').attr('font-size',9).attr('fill','var(--ink3)').text(y)
  })

  witnesses.value.forEach(w => {
    const x = xScale(w.year)
    const isSel = w.id === selectedWit.value
    const tickH = 14
    const tg = g.append('g').attr('transform',`translate(${x},0)`).style('cursor','pointer')
      .on('mouseenter', () => {
        const tip = tooltipEl.value
        if (!tip) return
        tip.textContent = `${w.id} — ${w.name} (${w.year})`
        tip.style.left = (margin.left + x) + 'px'
        tip.style.top = '2px'
        tip.classList.add('show')
      })
      .on('mouseleave', () => tooltipEl.value?.classList.remove('show'))
      .on('click', () => { selectedWit.value = w.id })

    tg.append('line').attr('x1',0).attr('y1',axisY-tickH).attr('x2',0).attr('y2',axisY)
      .attr('stroke', isSel ? 'var(--ink)' : 'var(--ink3)').attr('stroke-width', isSel ? 2 : 1).attr('opacity', isSel ? 1 : 0.55)
    tg.append('circle').attr('cx',0).attr('cy',axisY-tickH).attr('r', isSel ? 3 : 1.8)
      .attr('fill', isSel ? 'var(--ink)' : 'var(--ink3)').attr('opacity', isSel ? 1 : 0.6)
  })
}

onMounted(() => { draw(); window.addEventListener('resize', draw) })
onUnmounted(() => window.removeEventListener('resize', draw))
watch([selectedWit, witnesses], () => draw(), { deep: true })

defineExpose({ draw })
</script>

<style scoped>
.tl-tooltip { position:absolute; background:var(--ink); color:#fff; font-family:var(--mono); font-size:10px; padding:4px 7px; border-radius:3px; pointer-events:none; white-space:nowrap; z-index:20; opacity:0; transition:opacity .1s; transform:translateX(-50%); }
.tl-tooltip.show { opacity:1; }
</style>
