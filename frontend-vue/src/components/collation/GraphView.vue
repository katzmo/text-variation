<template>
  <div style="position: relative; overflow-x: auto; width: 100%">
    <svg ref="svgRef" :height="HEIGHT" style="display: block" />
    <div
      v-if="tooltip"
      :style="{
        position: 'fixed',
        left: tooltip.x + 10 + 'px',
        top: tooltip.y + 10 + 'px',
        backgroundColor: '#333',
        color: '#fff',
        padding: '6px 10px',
        borderRadius: '4px',
        fontSize: '12px',
        pointerEvents: 'none',
        zIndex: 1000,
      }"
    >
      {{ tooltip.translation }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as d3 from 'd3'
import { witnessColor } from '../../utils.js'

const props = defineProps({
  data: { type: Array, required: true },       // GraphPosition[]
  translationOrder: { type: Array, required: true },
  hoveredTranslation: { type: String, default: null },
  selectedWitness: { type: String, default: null },
  zoom: { type: Number, default: 1 },
})

const emit = defineEmits(['hover', 'select'])

// ── Constants ─────────────────────────────────────────────────────────────────
const X_STEP = 120
const HEIGHT = 750
const MARGIN = { top: 40, right: 120, bottom: 20, left: 20 }
const INNER_H = HEIGHT - MARGIN.top - MARGIN.bottom
const PILL_WIDTH = 14
const LANE_HEIGHT = 6

// ── DOM refs / state ──────────────────────────────────────────────────────────
const svgRef = ref(null)
const tooltip = ref(null)

// ── Pure layout helpers ───────────────────────────────────────────────────────
function getPillHeight(translationCount) {
  return Math.max(LANE_HEIGHT * translationCount, 16)
}

function getLaneY(nodeY, laneIndex, totalLanes) {
  const pillHeight = getPillHeight(totalLanes)
  const top = nodeY - pillHeight / 2
  return top + (laneIndex + 0.5) * (pillHeight / totalLanes)
}

function getInterpolatedLaneY(nodeY, laneIndex, totalLanes, zoom) {
  const detailY = getLaneY(nodeY, laneIndex, totalLanes)
  const sankeyY = nodeY
  return sankeyY * (1 - zoom) + detailY * zoom
}

function resolveCollisions(nodes) {
  const iterations = 20
  for (let iter = 0; iter < iterations; iter++) {
    nodes.sort((a, b) => a.y - b.y)
    let moved = false
    for (let i = 0; i < nodes.length - 1; i++) {
      const a = nodes[i]
      const b = nodes[i + 1]
      const minGap =
        getPillHeight(a.translations.length) / 2 +
        getPillHeight(b.translations.length) / 2 +
        24
      const overlap = minGap - (b.y - a.y)
      if (overlap > 0) {
        a.y -= overlap / 2
        b.y += overlap / 2
        moved = true
      }
    }
    if (!moved) break
  }
  nodes.forEach((n) => {
    const half = getPillHeight(n.translations.length) / 2
    n.y = Math.max(half, Math.min(INNER_H - half, n.y))
  })
}

function computeNodePositions(data, translationOrder) {
  const innerW = (data.length - 1) * X_STEP
  const xScale = d3
    .scalePoint()
    .domain(data.map((_, i) => i.toString()))
    .range([0, innerW])

  const translationY = (t) => {
    const idx = translationOrder.indexOf(t)
    const total = translationOrder.length
    return (idx / Math.max(total - 1, 1)) * INNER_H
  }

  const previousTranslationY = new Map()
  const nodes = []

  data.forEach((pos, pi) => {
    const x = xScale(pi.toString())

    const posNodes = pos.groups.map((group) => {
      const ys = group.translations.map(translationY).sort((a, b) => a - b)
      const mid = Math.floor(ys.length / 2)
      const medianY =
        ys.length % 2 !== 0 ? ys[mid] : (ys[mid - 1] + ys[mid]) / 2

      const previousYs = group.translations
        .map((t) => previousTranslationY.get(t))
        .filter((y) => y != null)

      const continuityY = previousYs.length > 0 ? d3.mean(previousYs) : medianY

      const continuityWeight = Math.min(
        0.99,
        0.7 + group.translations.length / translationOrder.length,
      )

      const y = continuityY * continuityWeight + medianY * (1 - continuityWeight)

      return {
        x,
        y,
        word: group.representative,
        translations: [...group.translations].sort(
          (a, b) => translationOrder.indexOf(a) - translationOrder.indexOf(b),
        ),
      }
    })

    posNodes.sort((a, b) => a.y - b.y)
    resolveCollisions(posNodes)

    const largestNode = posNodes.reduce((a, b) =>
      a.translations.length >= b.translations.length ? a : b,
    )
    const delta = INNER_H / 2 - largestNode.y
    posNodes.forEach((n) => {
      n.y += delta
    })

    posNodes.forEach((n) => {
      const half = getPillHeight(n.translations.length) / 2
      n.y = Math.max(half, Math.min(INNER_H - half, n.y))
    })

    posNodes.forEach((node) => {
      node.translations.forEach((t) => {
        previousTranslationY.set(t, node.y)
      })
    })

    nodes.push(posNodes)
  })

  return { nodes, xScale, innerW }
}

function buildPaths(data, nodes, translationOrder, zoom) {
  const verseTranslations = new Set(
    data.flatMap((p) => p.groups.flatMap((g) => g.translations)),
  )
  const sorted = translationOrder.filter((t) => verseTranslations.has(t))

  return sorted.map((translation) => {
    const points = []
    data.forEach((_, pi) => {
      const node = nodes[pi].find((n) => n.translations.includes(translation))
      if (!node) return
      const laneIndex = node.translations.indexOf(translation)
      const y = getInterpolatedLaneY(node.y, laneIndex, node.translations.length, zoom)
      points.push({ x: node.x - PILL_WIDTH / 2, y })
      points.push({ x: node.x + PILL_WIDTH / 2, y })
    })
    return { translation, points }
  })
}

function buildFlows(data, nodes) {
  const flows = []
  data.forEach((_, pi) => {
    if (pi === data.length - 1) return
    nodes[pi].forEach((fromNode) => {
      const destinations = new Map()
      fromNode.translations.forEach((t) => {
        const toNode = nodes[pi + 1].find((n) => n.translations.includes(t))
        if (!toNode) return
        if (!destinations.has(toNode)) destinations.set(toNode, [])
        destinations.get(toNode).push(t)
      })
      destinations.forEach((translations, toNode) => {
        flows.push({ fromNode, toNode, translations })
      })
    })
  })
  return flows
}

function ribbonPath(x0, y0, x1, y1, bandHeight) {
  const cx0 = x0 + (x1 - x0) * 0.4
  const cx1 = x0 + (x1 - x0) * 0.6
  const half = bandHeight / 2
  return [
    `M ${x0} ${y0 - half}`,
    `C ${cx0} ${y0 - half}, ${cx1} ${y1 - half}, ${x1} ${y1 - half}`,
    `L ${x1} ${y1 + half}`,
    `C ${cx1} ${y1 + half}, ${cx0} ${y0 + half}, ${x0} ${y0 + half}`,
    `Z`,
  ].join(' ')
}

// ── Draw ──────────────────────────────────────────────────────────────────────
function drawGraph() {
  if (!svgRef.value || props.data.length === 0) return

  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

  const { nodes, xScale, innerW } = computeNodePositions(props.data, props.translationOrder)
  const totalWidth = innerW + MARGIN.left + MARGIN.right
  svg.attr('width', totalWidth).attr('height', HEIGHT)

  const flows = buildFlows(props.data, nodes)
  const paths = buildPaths(props.data, nodes, props.translationOrder, 1)

  const line = d3
    .line()
    .x((d) => d.x)
    .y((d) => d.y)
    .curve(d3.curveBumpX)

  // ── Sankey layer ──────────────────────────────────────────────────────────
  const sankeyGroup = g.append('g').attr('class', 'sankey').attr('opacity', 1 - props.zoom)

  flows.forEach(({ fromNode, toNode, translations }) => {
    const fromIndices = translations
      .map((t) => fromNode.translations.indexOf(t))
      .filter((i) => i !== -1)
      .sort((a, b) => a - b)
    const toIndices = translations
      .map((t) => toNode.translations.indexOf(t))
      .filter((i) => i !== -1)
      .sort((a, b) => a - b)

    const fromMidLane = fromIndices[Math.floor(fromIndices.length / 2)]
    const toMidLane = toIndices[Math.floor(toIndices.length / 2)]
    const fromY = getLaneY(fromNode.y, fromMidLane, fromNode.translations.length)
    const toY = getLaneY(toNode.y, toMidLane, toNode.translations.length)
    const bandHeight = translations.length * LANE_HEIGHT

    sankeyGroup
      .append('path')
      .attr('d', ribbonPath(fromNode.x + PILL_WIDTH / 2, fromY, toNode.x - PILL_WIDTH / 2, toY, bandHeight))
      .attr('fill', '#ccc')
      .attr('fill-opacity', 0.6)
      .attr('stroke', '#ccc')
      .attr('stroke-width', 0.5)
      .attr('stroke-opacity', 0.8)
  })

  // ── Lines layer ───────────────────────────────────────────────────────────
  const edgeGroup = g.append('g').attr('class', 'edges').attr('opacity', props.zoom)

  paths.forEach(({ translation, points }) => {
    if (points.length < 2) return
    edgeGroup
      .append('path')
      .datum(points)
      .attr('fill', 'none')
      .attr('stroke', witnessColor(translation))
      .attr('stroke-width', 4)
      .attr('stroke-opacity', 0.5)
      .attr('d', line)
      .attr('class', `path-${CSS.escape(translation)}`)
      .style('cursor', 'pointer')
      .on('mouseenter', function (event) {
        tooltip.value = { x: event.clientX, y: event.clientY, translation }
        emit('hover', translation)
      })
      .on('mouseleave', () => {
        tooltip.value = null
        emit('hover', null)
      })
      .on('click', () => {
        emit('select', translation)
      })
  })

  edgeGroup.style('mix-blend-mode', 'multiply')
  applyHighlight()

  // ── Axis lines ────────────────────────────────────────────────────────────
  props.data.forEach((_, pi) => {
    const x = xScale(pi.toString())
    g.append('line')
      .attr('x1', x).attr('x2', x)
      .attr('y1', 0).attr('y2', INNER_H)
      .attr('stroke', '#ccc').attr('stroke-width', 1)
  })

  // ── Nodes (pills) ─────────────────────────────────────────────────────────
  props.data.forEach((_, pi) => {
    const sortedBySize = [...nodes[pi]].sort(
      (a, b) => b.translations.length - a.translations.length,
    )
    sortedBySize.forEach((node) => {
      const pillHeight = getPillHeight(node.translations.length)
      const pillX = node.x - PILL_WIDTH / 2
      const pillY = node.y - pillHeight / 2
      const radius = PILL_WIDTH / 2
      const isEmpty = node.word === '-'

      g.append('rect')
        .attr('x', pillX).attr('y', pillY)
        .attr('width', PILL_WIDTH).attr('height', pillHeight)
        .attr('rx', radius).attr('ry', radius)
        .attr('fill', '#e8e8e8')
        .attr('stroke', '#ccc')
        .attr('stroke-width', 1)
        .attr('opacity', isEmpty ? 0.5 : 1.0)

      g.append('text')
        .attr('x', node.x).attr('y', pillY - 6)
        .attr('text-anchor', 'middle')
        .attr('font-size', '11px')
        .attr('fill', '#444')
        .attr('opacity', isEmpty ? 0.5 : 1.0)
        .text(node.word === '-' ? '∅' : node.word)
    })
  })
}

// ── Highlighting ──────────────────────────────────────────────────────────────
// Hover takes precedence over the persistent witness selection.
function applyHighlight() {
  if (!svgRef.value) return
  const translation = props.hoveredTranslation || props.selectedWitness
  const edgeGroup = d3.select(svgRef.value).select('.edges')
  if (translation) {
    edgeGroup.selectAll('path').attr('stroke-opacity', 0.30).attr('stroke-width', 4)
    edgeGroup.select(`.path-${CSS.escape(translation)}`).attr('stroke-opacity', 1).attr('stroke-width', 4).raise()
  } else {
    edgeGroup.selectAll('path').attr('stroke-opacity', 0.35).attr('stroke-width', 4)
  }
}

// ── Watchers ──────────────────────────────────────────────────────────────────
watch(() => [props.data, props.translationOrder], drawGraph, { deep: true })

watch(() => [props.hoveredTranslation, props.selectedWitness], applyHighlight)

watch(
  () => props.zoom,
  (zoom) => {
    if (!svgRef.value) return
    const svg = d3.select(svgRef.value)
    svg.select('.edges').attr('opacity', zoom)
    svg.select('.sankey').attr('opacity', 1 - zoom)
  },
)

onMounted(drawGraph)
</script>
