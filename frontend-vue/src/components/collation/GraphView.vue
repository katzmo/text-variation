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
        whiteSpace: 'pre-line',
      }"
    >
      {{ tooltip.text }}
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import * as d3 from 'd3'
import { witnessColor } from '../../utils.js'

const props = defineProps({
  data: { type: Array, required: true }, // GraphPosition[]
  translationOrder: { type: Array, required: true },
  hoveredTranslation: { type: String, default: null },
  selectedWitness: { type: String, default: null },
  zoom: { type: Number, default: 1 },
  showMerged: { type: Boolean, default: false },
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
  const bundledY = nodeY
  return bundledY * (1 - zoom) + detailY * zoom
}

// zoom = 1 -> full lane-based pill height (detail); zoom = 0 -> collapses to a
// small circle (width == height) matching the bundled lines converging on it.
function getInterpolatedPillHeight(translationCount, zoom) {
  const detailHeight = getPillHeight(translationCount)
  const bundledHeight = PILL_WIDTH
  return bundledHeight * (1 - zoom) + detailHeight * zoom
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
        getPillHeight(a.translations.length) / 2 + getPillHeight(b.translations.length) / 2 + 24
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
      const medianY = ys.length % 2 !== 0 ? ys[mid] : (ys[mid - 1] + ys[mid]) / 2

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
        readings: group.readings,
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
  const verseTranslations = new Set(data.flatMap((p) => p.groups.flatMap((g) => g.translations)))
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

// A pill's word is just the majority reading; when the merge threshold fuses
// distinct spellings into one group, the minority readings are otherwise
// invisible. Break the group down by distinct word, most frequent first, so
// it can be surfaced on hover and (optionally) as stacked labels.
function getWordBreakdown(node) {
  if (!node.readings) return [{ word: node.word, wits: node.translations }]
  const byWord = new Map()
  node.translations.forEach((t) => {
    const word = node.readings[t] ?? node.word
    if (!byWord.has(word)) byWord.set(word, [])
    byWord.get(word).push(t)
  })
  return [...byWord.entries()]
    .map(([word, wits]) => ({ word, wits }))
    .sort((a, b) => b.wits.length - a.wits.length)
}

// Returns null when the group has no more than one distinct reading (nothing
// merged away, so there's nothing extra to show).
function buildNodeTooltip(node) {
  const breakdown = getWordBreakdown(node)
  if (breakdown.length <= 1) return null
  return breakdown
    .map(({ word, wits }) => `${word === '-' ? '∅' : word}: ${wits.join(', ')}`)
    .join('\n')
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

  // zoom = 1 spreads each witness into its own lane (full detail); zoom = 0
  // collapses every witness in a node onto the same point, so overlapping
  // lines read as a single bundled flow between nodes.
  const paths = buildPaths(props.data, nodes, props.translationOrder, props.zoom)

  const line = d3
    .line()
    .x((d) => d.x)
    .y((d) => d.y)
    .curve(d3.curveBumpX)

  // ── Lines layer ───────────────────────────────────────────────────────────
  const edgeGroup = g.append('g').attr('class', 'edges')

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
        tooltip.value = { x: event.clientX, y: event.clientY, text: translation }
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
      .attr('x1', x)
      .attr('x2', x)
      .attr('y1', 0)
      .attr('y2', INNER_H)
      .attr('stroke', '#ccc')
      .attr('stroke-width', 1)
  })

  // ── Nodes (pills) ─────────────────────────────────────────────────────────
  props.data.forEach((_, pi) => {
    const sortedBySize = [...nodes[pi]].sort(
      (a, b) => b.translations.length - a.translations.length,
    )
    sortedBySize.forEach((node) => {
      const pillHeight = getInterpolatedPillHeight(node.translations.length, props.zoom)
      const pillX = node.x - PILL_WIDTH / 2
      const pillY = node.y - pillHeight / 2
      const radius = PILL_WIDTH / 2
      const isEmpty = node.word === '-'
      const nodeTooltip = buildNodeTooltip(node)

      g.append('rect')
        .attr('x', pillX)
        .attr('y', pillY)
        .attr('width', PILL_WIDTH)
        .attr('height', pillHeight)
        .attr('rx', radius)
        .attr('ry', radius)
        .attr('fill', '#e8e8e8')
        .attr('stroke', '#ccc')
        .attr('stroke-width', 1)
        .attr('opacity', isEmpty ? 0.5 : 1.0)
        .style('cursor', nodeTooltip ? 'help' : null)
        .on('mouseenter', (event) => {
          if (!nodeTooltip) return
          tooltip.value = { x: event.clientX, y: event.clientY, text: nodeTooltip }
        })
        .on('mouseleave', () => {
          if (nodeTooltip) tooltip.value = null
        })

      // With showMerged on, stack every distinct reading above the node instead
      // of collapsing to the majority word — most frequent nearest the pill.
      const stacked = props.showMerged ? getWordBreakdown(node) : null
      if (stacked && stacked.length > 1) {
        const LABEL_LINE_H = 11
        stacked.forEach(({ word }, i) => {
          g.append('text')
            .attr('x', node.x)
            .attr('y', pillY - 6 - i * LABEL_LINE_H)
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .attr('fill', '#444')
            .attr('opacity', word === '-' ? 0.5 : 1.0)
            .text(word === '-' ? '∅' : word)
        })
      } else {
        g.append('text')
          .attr('x', node.x)
          .attr('y', pillY - 6)
          .attr('text-anchor', 'middle')
          .attr('font-size', '11px')
          .attr('fill', '#444')
          .attr('opacity', isEmpty ? 0.5 : 1.0)
          .text(node.word === '-' ? '∅' : node.word)
      }
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
    edgeGroup.selectAll('path').attr('stroke-opacity', 0.3).attr('stroke-width', 4)
    edgeGroup
      .select(`.path-${CSS.escape(translation)}`)
      .attr('stroke-opacity', 1)
      .attr('stroke-width', 4)
      .raise()
  } else {
    edgeGroup.selectAll('path').attr('stroke-opacity', 0.35).attr('stroke-width', 4)
  }
}

// ── Watchers ──────────────────────────────────────────────────────────────────
// zoom changes node y-positions (see buildPaths), so it needs a full redraw,
// not just an attribute tweak.
watch(
  () => [props.data, props.translationOrder, props.zoom, props.showMerged],
  drawGraph,
  { deep: true },
)

watch(() => [props.hoveredTranslation, props.selectedWitness], applyHighlight)

onMounted(drawGraph)
</script>
