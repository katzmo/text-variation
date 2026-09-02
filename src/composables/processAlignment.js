import { useIndexedDBStore } from '@/composables/db'

/**
 * A composable for matching and scoring segments for similarity.
 * @returns {Object} An object containing alignment-related functions.
 */
export function useAlignmentProcessor() {
  const { db, dbExec } = useIndexedDBStore()

  /**
   * Align each document with every other.
   *
   * @param {Object} [options] - Configuration options.
   * @param {number} [options.topK=10] - Number of top candidates to consider.
   */
  const alignSegments = async (options = {}) => {
    const docKeys = await dbExec('documents', 'getAllKeys')
    await Promise.all(
      docKeys.flatMap((doc1, i) =>
        docKeys.slice(i + 1).map(async (doc2) => alignPair(doc1, doc2, options)),
      ),
    )
  }

  /**
   * Aligns segments between two documents.
   *
   * @param {string} docKey1 - First document key.
   * @param {string} docKey2 - Second document key.
   * @param {Object} [options] - Configuration options.
   * @param {number} [options.topK=10] - Number of top candidates to consider.
   * @returns {Promise<Array>} Array of [segKey1, segKey2, score] tuples.
   */
  const alignPair = async (docKey1, docKey2, options = {}) => {
    const existing = await db.getFromIndex('scores', 'docKeys', [docKey1, docKey2])
    if (existing) return
    // Find matching segments in the documents
    const candidates = await findCandidates(docKey1, docKey2)
    // Process and filter candidates
    const filteredScores = filterTopCandidates(candidates, options.topK)
    // Store the best matches
    await saveTopScores(filteredScores, [docKey1, docKey2])
  }

  /**
   * Finds segments that share the same tokens in two documents.
   *
   * @param {Array} docKey1 - Key of the first document.
   * @param {string} docKey2 - Key of the second document.
   * @returns {Object} Candidate pairs with shared token counts.
   */
  const findCandidates = async (docKey1, docKey2) => {
    const candidates = {}
    const store = db.transaction('tokens', 'readonly').store
    for await (const cursor of store.index('docKey').iterate(docKey1)) {
      const token1 = cursor.value
      const token2 = await store.index('idByDoc').get([token1.id, docKey2])
      if (token2) {
        for (const segKey1 of token1.segKeys) {
          candidates[segKey1] ??= {}
          for (const segKey2 of token2.segKeys) {
            candidates[segKey1][segKey2] = (candidates[segKey1][segKey2] ?? 0) + 1
          }
        }
      }
    }
    return candidates
  }

  /**
   * Filter candidate pairs to get the most promising alignments.
   *
   * @param {Object} candidates - Candidate pairs with counts.
   * @param {number} [topK=10] - Number of top candidates per segment.
   * @returns {Array} Array of [segKey1, segKey2, score] tuples.
   */
  const filterTopCandidates = (candidates, topK = 10) => {
    const scores = []
    for (const [segKey1, candidates2] of Object.entries(candidates)) {
      Object.entries(candidates2)
        .sort((a, b) => b[1] - a[1]) // sorts by count descending
        .slice(0, topK) // keeps only the top k candidates
        .forEach(([segKey2, value]) => {
          scores.push([segKey1, segKey2, value])
        })
    }
    return scores
  }

  /**
   * Stores the best available alignments in the database.
   *
   * @param {Array} scores - Array of [segKey1, segKey2, score] tuples.
   * @param {Array} docKeys - Tuple of the 2 related document keys.
   */
  const saveTopScores = async (scores, docKeys) => {
    const tx = db.transaction('scores', 'readwrite')
    // Keep track of already aligned segments.
    const aligned = [new Set(), new Set()]
    // Sort by scores descending.
    scores.sort((a, b) => b[2] - a[2])
    // Pick the best available pairing for unaligned segments.
    for (const [segKey1, segKey2, score] of scores) {
      if (!aligned[0].has(segKey1) && !aligned[1].has(segKey2)) {
        tx.store.add({
          docKeys: docKeys,
          segKeys: [segKey1, segKey2].sort(),
          score,
        })
        aligned[0].add(segKey1)
        aligned[1].add(segKey2)
      }
    }
    await tx.done
  }

  return {
    alignSegments,
    alignPair,
    filterTopCandidates,
    saveTopScores,
  }
}
