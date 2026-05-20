<template>
  <div class="panel" style="min-height:180px;max-height:220px;">
    <div class="panel-header">
      <span class="panel-title">{{ title }}</span>
      <div class="panel-expand" @click="$emit('expand', title)">⤢</div>
    </div>
    <div class="panel-body" ref="containerEl">
      <svg ref="svgEl" style="display:block;width:100%;height:100%;"></svg>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { useStore } from '../../composables/useStore.js'

const props = defineProps({ title: String, groupBy: String })
defineEmits(['expand'])
const { witnesses, selectedWit } = useStore()
const containerEl = ref(null); const svgEl = ref(null)

function buildData() {
  const sel = witnesses.value.find(w => w.id === selectedWit.value)
  const selVal = sel?.[props.groupBy] || ''
  const groups = d3.group(witnesses.value, w => w[props.groupBy])

  const ORDER_AFF  = ['Protestant','Evangelical','Catholic','Anglican','Inter-denom.','Other']
  const order = props.groupBy === 'affiliation' ? ORDER_AFF : null

  let entries = order
    ? order.filter(k => groups.has(k)).map(k => [k, groups.get(k)])
    : [...groups.entries()].sort((a,b) => b[1].length - a[1].length)
  if (order) groups.forEach((wits, key) => { if (!order.includes(key)) entries.push([key, wits]) })

  return entries.map(([key, wits]) => ({
    label: key.length > 22 ? key.slice(0, 20) + '…' : key,
    total: wits.length,
    selected: wits.filter(w => w[props.groupBy] === selVal).length,
    ids: wits.map(w => w.id),
  }))
}

function draw() {
  const el = containerEl.value; const svg = svgEl.value
  if (!el || !svg) return
  const data = buildData()
  const W = el.clientWidth || 240; const H = el.clientHeight || 160
  const margin = { top: 6, right: 36, bottom: 6, left: 90 }
  const iW = W - margin.left - margin.right
  const barH = 13; const gap = 6
  const xMax = d3.max(data, d => d.total) || 1
  const xScale = d3.scaleLinear().domain([0, xMax]).range([0, iW])
  const totalH = data.length * (barH + gap) + margin.top + margin.bottom

  const s = d3.select(svg).attr('width', W).attr('height', Math.max(H, totalH))
  s.selectAll('*').remove()
  const g = s.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

  data.forEach((d, i) => {
    const y = i * (barH + gap)
    const isActive = d.ids.includes(selectedWit.value)
    g.append('text').attr('x', -6).attr('y', y + barH / 2 + 4).attr('text-anchor', 'end')
      .attr('font-family', 'var(--sans)').attr('font-size', 10)
      .attr('fill', isActive ? 'var(--ink)' : 'var(--ink2)').attr('font-weight', isActive ? 600 : 400).text(d.label)
    g.append('rect').attr('x', 0).attr('y', y).attr('width', iW).attr('height', barH).attr('fill', 'var(--bg)').attr('rx', 2)
    g.append('rect').attr('x', 0).attr('y', y).attr('width', xScale(d.total)).attr('height', barH).attr('fill', '#ccc4b4').attr('rx', 2)
    if (d.selected > 0) g.append('rect').attr('x', 0).attr('y', y).attr('width', xScale(d.selected)).attr('height', barH).attr('fill', 'var(--ink)').attr('rx', 2)
    g.append('text').attr('x', xScale(d.total) + 4).attr('y', y + barH / 2 + 4).attr('font-family', 'var(--mono)').attr('font-size', 9).attr('fill', 'var(--ink3)').text(d.total)
  })
}

onMounted(() => { draw(); window.addEventListener('resize', draw) })
onUnmounted(() => window.removeEventListener('resize', draw))
watch([selectedWit, witnesses], () => draw(), { deep: true })
defineExpose({ draw })
</script>
