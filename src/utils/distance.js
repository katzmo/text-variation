/**
 * @module Edit distance.
 * @description Calculate the distance between two strings on word level.
 */

/**
 * Restricted Damerau–Levenshtein distance (optimal string alignment).
 *
 * Supports insertions, deletions, substitutions and adjacent transpositions
 * while each substring may only be transformed once.
 * When a max cost is given, the function only calculates edit paths within it.
 *
 * @param {Array} sequenceA - An array of words or characters.
 * @param {Array} sequenceB - Another array of words or characters.
 * @param {Object} [options] - Configuration options.
 * @param {number} [options.maxCost=100] - Maximum allowed cost, discard if higher.
 * @param {Function} [options.substitutionFunc=(a, b) => (a === b ? 0 : 1)]
 *   - A custom function for calculating substitution costs.
 * @returns {number|null} - The calculated edit distance if <= maxCost.
 */
export function getEditDistance(sequenceA, sequenceB, options = {}) {
  const { maxCost = 100, substitutionFunc = (a, b) => (a === b ? 0 : 1) } = options
  const [source, target] =
    sequenceB.length > sequenceA.length ? [sequenceA, sequenceB] : [sequenceB, sequenceA]

  if (target.length - source.length > maxCost) return null
  if (source.length === 0) return target.length

  let previousRow = Array.from({ length: target.length + 1 }, (_, j) => j)
  let earlierRow

  for (let i = 0; i < source.length; i++) {
    const currentRow = new Array(target.length + 1).fill(maxCost + 1)
    if (i < maxCost) currentRow[0] = i + 1
    let currentRowMin = maxCost + 1

    for (let j = 0; j < target.length; j++) {
      const substitutionCost = previousRow[j] + substitutionFunc(source[i], target[j])
      const deletionCost = currentRow[j] + 1
      const insertionCost = previousRow[j + 1] + 1

      let minCost = Math.min(substitutionCost, deletionCost, insertionCost)

      // Adjacent transposition
      if (i >= 1 && j >= 1 && source[i] === target[j - 1] && source[i - 1] === target[j]) {
        const transposition = earlierRow[j - 1] + 1
        minCost = Math.min(minCost, transposition)
      }
      if (minCost < currentRowMin) currentRowMin = minCost
      currentRow[j + 1] = minCost
    }
    // Still within cost limit?
    if (currentRowMin > maxCost) return null

    earlierRow = previousRow
    previousRow = currentRow
  }

  const distance = previousRow[target.length]
  return distance > maxCost ? null : distance
}

/**
 * Strips shared parts from the start and end of two sequences.
 *
 * @param {string} sequenceA - An array of words or characters.
 * @param {string} sequenceB - Another array of words or characters.
 * @returns {string} - The stripped sequence inbetween.
 */
export function stripShared(sequenceA, sequenceB) {
  let start = 0
  let endA = sequenceA.length
  let endB = sequenceB.length
  while (start < Math.max(endA, endB) && sequenceA[start] === sequenceB[start]) start++
  while (endA > start && endB > start && sequenceA[endA - 1] === sequenceB[endB - 1]) {
    endA--
    endB--
  }
  return [sequenceA.slice(start, endA), sequenceB.slice(start, endB)]
}

/**
 * Converts a distance to a similarity value in [0, 1].
 *
 * @param {Array} sequenceA - An array of words or characters.
 * @param {Array} sequenceB - Another array of words or characters.
 * @param {Object} [options] - Configuration options.
 * @param {number} [options.threshold=0] - Similarity threshold for scores in [0, 1].
 * @return {number} - A score in [0, 1].
 */
export function getNormalizedDistance(sequenceA, sequenceB, options = {}) {
  const { threshold = 0 } = options
  const maxLength = Math.max(sequenceA.length, sequenceB.length)
  const maxCost = Math.round(maxLength - maxLength * threshold)
  const shortenedSequences = stripShared(sequenceA, sequenceB)
  const distance = getEditDistance(...shortenedSequences, { maxCost })
  return distance === null ? 0 : 1 - distance / maxLength
}

/**
 * Hybrid word/character similarity.
 *
 * @param {string} textA - One text segment.
 * @param {string} textB - Another text segment.
 * @param {Object} [options] - Configuration options.
 * @param {number} [options.threshold=0] - Minimum similarity for scores.
 * @return {number} - A normalized score between 0 and 1.
 */
export function getSimilarityScore(textA, textB, options = {}) {
  const wordsA = textA.trim().split(/\s+/)
  const wordsB = textB.trim().split(/\s+/)
  return getNormalizedDistance(wordsA, wordsB, options)
  }
  return getNormalizedDistance(wordsA, wordsB, { threshold, substitutionFunc })
}
