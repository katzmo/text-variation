import { ref } from 'vue'
import { asc } from '@/utils/utils'
import { useIndexedDBStore } from '@/composables/db'

const referenceDoc = ref(null)
const scoreColors = ref(['var(--color-score-0)', 'var(--color-score-100)'])

/**
 * A composable assigning a score to grouped elements.
 *
 * @param {Object} wrapper - A ref object of the DOM wrapper element.
 * @param {Object} [options] - Configuration options for score behavior.
 * @param {number} [options.classes] - Array of score class names, starting lowest.
 * @returns {Object} An object containing score-related functions and reactive properties.
 */
export function useScores(wrapper, options = {}) {
  const { db } = useIndexedDBStore()

  /**
   * Get current segment scores and group IDs for a document.
   *
   * @param {Number} docKey - Key of the document to update.
   * @returns {Promise<Map>} Resolves to a map of <segKey: {scores, id}>
   */
  const getScores = async (docKey) => {
    const tx = db.transaction(['groups', 'scores'], 'readonly')
    const scoreIndex = referenceDoc.value ? 'docKeys' : 'docKey'
    const scoreValue = referenceDoc.value ? [docKey, referenceDoc.value.key].sort(asc) : docKey
    const [scores, groups] = await Promise.all([
      tx.objectStore('scores').index(scoreIndex).getAll(scoreValue),
      tx.objectStore('groups').index('docKey').getAll(docKey),
    ])
    await tx.done
    const segScores = new Map(groups.map((g) => [g.segKey, { groupId: g.id, scores: [] }]))
    for (const { segKeys, score } of scores) {
      // Only one segKey belongs to this document but we don‘t know which one.
      segKeys.forEach((segKey) => segScores.get(segKey)?.scores.push(score))
    }
    return segScores
  }

  /**
   * Set segment background-colors according to their current score.
   *
   * @param {Number} docKey - Key of the document to update.
   * @param {Array<string>} [colors] - A list of background colors (different to similar).
   * @returns {Promise<void>} Resolves when scores have been updated.
   */
  const updateScores = async (docKey, colors = scoreColors.value) => {
    const segScores = await getScores(docKey)
    const getColor =
      colors.length === 2
        ? (score) => `color-mix(in oklch, ${colors[1]} ${score * 100}%, ${colors[0]})` // continous scale
        : (score) => colors[Math.floor(score * (colors.length - 1))] // discrete scale (last value == 100%)
    segScores.forEach(({ scores, groupId }) => {
      const score = scores.reduce((a, b) => a + b, 0) / scores.length // average score
      const element = wrapper.value?.querySelector(`[data-group="${groupId}"]`)
      if (element) {
        element.dataset.score = Math.floor(score * 100)
        element.style.setProperty('--color-segment', getColor(score))
      }
    })
    if (docKey === referenceDoc.value?.key) {
      wrapper.value?.querySelectorAll(`[data-group]`).forEach((element) => {
        element.dataset.score = 100
        element.style.setProperty('--color-segment', getColor(1))
      })
    }
  }

  return {
    referenceDoc,
    scoreColors,
    getScores,
    updateScores,
  }
}
