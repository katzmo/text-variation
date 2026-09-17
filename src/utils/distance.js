/**
 * @module Edit distance.
 * @description Calculate the distance between two strings using a hybrid
 *   approach where distance on word level is combined with the character-level
 *   distance of substitutions.
 */

/**
 * Restricted Damerau–Levenshtein distance (optimal string alignment).
 *
 * Supports insertions, deletions, substitutions with customizable cost and
 * adjacent transpositions while each substring may only be transformed once.
 *
 * @param {Array} sequenceA - An array of words or characters.
 * @param {Array} sequenceB - Another array of words or characters.
 * @param {Function} [substitutionFunc=(a, b) => (a === b ? 0 : 1)]
 *   - A custom function for calculating substitution costs in [0,1].
 * @returns {number} - The calculated edit distance.
 */
export function getEditDistance(sequenceA, sequenceB, substitutionFunc) {
  if (sequenceA.length === 0) return sequenceB.length
  if (sequenceB.length === 0) return sequenceA.length

  substitutionFunc ??= (a, b) => (a === b ? 0 : 1)

  const [source, target] =
    sequenceB.length > sequenceA.length ? [sequenceA, sequenceB] : [sequenceB, sequenceA]
  let previousRow = Array.from({ length: target.length + 1 }, (_, j) => j)
  let earlierRow

  for (let i = 0; i < source.length; i++) {
    const currentRow = new Array(target.length + 1)
    currentRow[0] = i + 1

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

      currentRow[j + 1] = minCost
    }

    earlierRow = previousRow
    previousRow = currentRow
  }
  return previousRow[target.length]
}

/**
 * Converts a distance to a similarity value in [0, 1].
 *
 * @param {Array} sequenceA - An array of words or characters.
 * @param {Array} sequenceB - Another array of words or characters.
 * @param {Function} [substitutionFunc] - A custom cost function for substitutions.
 * @return {number} - A score in [0, 1].
 */
export function getNormalizedDistance(sequenceA, sequenceB, substitutionFunc) {
  const distance = getEditDistance(sequenceA, sequenceB, substitutionFunc)
  return Math.max(0, 1 - distance / Math.max(sequenceA.length, sequenceB.length))
}

/**
 * Hybrid word/character similarity.
 *
 * @param {string} textA - One text segment.
 * @param {string} textB - Another text segment.
 * @return {number} - A normalized score between 0 and 1.
 */
export function getSimilarityScore(textA, textB) {
  const wordsA = textA.trim().split(/\s+/)
  const wordsB = textB.trim().split(/\s+/)

  return getNormalizedDistance(
    wordsA,
    wordsB,
    // Similar words receive a partial substitution cost.
    (wordA, wordB) => {
      if (wordA === wordB) return 0
      if (wordA.toLowerCase() === wordB.toLowerCase()) return 0.1
      return 1 - getNormalizedDistance(Array.from(wordA), Array.from(wordB))
    },
  )
}
