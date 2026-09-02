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
    const candidates = await Promise.all(
      docKeys.flatMap((doc1, i) =>
        docKeys.slice(i + 1).map(async (doc2) => alignPair(doc1, doc2, options)),
      ),
    )
    const sorted = candidates.flat().sort((a, b) => b[2] - a[2])
    await saveGroups(sorted)
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
    return filterTopCandidates(candidates, options.topK)
  }

  /**
   * Finds segments that share the same tokens in two documents.
   *
   * @param {Array} docKey1 - Key of the first document.
   * @param {string} docKey2 - Key of the second document.
   * @returns {Object} Candidate pairs with shared token counts.
   */
  const findCandidates = async (docKey1, docKey2) => {
    const candidates = { [docKey1]: {} }
    const store = db.transaction('tokens', 'readonly').store
    for await (const cursor of store.index('docKey').iterate(docKey1)) {
      const token1 = cursor.value
      const token2 = await store.index('idByDoc').get([token1.id, docKey2])
      if (token2) {
        for (const segKey1 of token1.segKeys) {
          candidates[docKey1][segKey1] ??= { [docKey2]: {} }
          for (const segKey2 of token2.segKeys) {
            candidates[docKey1][segKey1][docKey2][segKey2] ??= 0
            candidates[docKey1][segKey1][docKey2][segKey2] += 1
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
   * @returns {Array} Array of [[docKey1, segKey1], [docKey2, segKey2], score] tuples.
   */
  const filterTopCandidates = (candidates, topK = 10) => {
    const scores = []
    // Flatten nested objects.
    for (const [docKey1, segments1] of Object.entries(candidates)) {
      for (const [segKey1, candidates2] of Object.entries(segments1)) {
        for (const [docKey2, segments2] of Object.entries(candidates2)) {
          Object.entries(segments2)
            .sort((a, b) => b[1] - a[1]) // sorts by count descending
            .slice(0, topK) // keeps only the top k candidates
            .forEach(([segKey2, value]) => {
              scores.push([[docKey1, segKey1], [docKey2, segKey2], value])
            })
        }
      }
    }
    return scores
  }

  /**
   * Greedily sort related alignments into groups and store them.
   *
   * @param {Array} scores - Array of candidate tuples, sorted by score.
   *   Expected format: [[docKey1, segKey1], [docKey2, segKey2], score]
   */
  const saveGroups = async (scores) => {
    let tx = db.transaction('scores', 'readwrite')

    // Keep track of already aligned segments.
    const groupedSegs = new Map()
    const addToGroup = (group, docKey, segKey) => {
      group.documents.add(docKey)
      group.segments.add(segKey)
      groupedSegs.set(segKey, group)
    }

    // Pick the best available pairing for unaligned segments.
    for (const [[docKey1, segKey1], [docKey2, segKey2], score] of scores) {
      const group1 = groupedSegs.get(segKey1)
      const group2 = groupedSegs.get(segKey2)
      // Discard this pair if a segment from the same document has already been aligned.
      if (group1?.documents.has(docKey2) || group2?.documents.has(docKey1)) continue
      // Try to add the pair to a group.
      if (!group1 && !group2) {
        const newGroup = { id: generateId(), documents: new Set(), segments: new Set() }
        addToGroup(newGroup, docKey1, segKey1)
        addToGroup(newGroup, docKey2, segKey2)
      } else if (group1 && !group2) {
        addToGroup(group1, docKey2, segKey2)
      } else if (!group1 && group2) {
        addToGroup(group2, docKey1, segKey1)
      } else if (group1 !== group2) {
        // Merge if no segments are from the same document.
        if (group1.documents.intersection(group2.documents).size) continue
        const segArray = [...group2.segments]
        Array.from(group2.documents).forEach((docKey, i) => {
          addToGroup(group1, docKey, segArray[i])
        })
      }
      // Pair was added to a group -> save score.
      tx.store.add({
        docKeys: [docKey1, docKey2].sort(),
        segKeys: [segKey1, segKey2].sort(),
        score,
      })
    }
    await tx.done

    // Save groups.
    const groups = new Set(groupedSegs.values())
    tx = db.transaction('groups', 'readwrite')
    groups.forEach(({ id, segments }) => {
      tx.store.add({ id, segKeys: [...segments].sort() })
    })
  }

  /**
   * Generate a short random string.
   *
   * @param {int} [length=8] - The length of the output.
   * @returns {string} - A random base36 string.
   */
  const generateId = (length = 8) => {
    return Math.random()
      .toString(36)
      .substring(2, length + 2)
  }

  return {
    alignSegments,
    alignPair,
    filterTopCandidates,
    saveGroups,
  }
}
