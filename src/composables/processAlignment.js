import { asc, desc, generateId } from '@/utils'
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
   * @returns {Promise<void>} - Segments have been aligned, grouped and scored.
   */
  const alignSegments = async (options = {}) => {
    const docKeys = await dbExec('documents', 'getAllKeys')
    const candidates = await Promise.all(
      docKeys.flatMap((doc1, i) =>
        docKeys.slice(i + 1).map((doc2) => alignPair(doc1, doc2, options)),
      ),
    )
    const sorted = candidates
      .flat()
      .filter((val) => val)
      .sort((a, b) => desc(a[2], b[2]))
    return pickScores(sorted)
  }

  /**
   * Aligns segments between two documents.
   *
   * @param {string} docKey1 - First document key.
   * @param {string} docKey2 - Second document key.
   * @param {Object} [options] - Configuration options.
   * @param {number} [options.topK=10] - Number of top candidates to consider.
   * @returns {Promise<Array>} Array of [docKey1, segKey1], [docKey2, segKey2], value] tuples.
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
   * @param {string} docKey1 - Key of the first document.
   * @param {string} docKey2 - Key of the second document.
   * @returns {Promise<Map>} - Candidate pairs with shared token counts.
   */
  const findCandidates = async (docKey1, docKey2) => {
    const candidates = new Map()
    const store = db.transaction('tokens', 'readonly').store
    for await (const cursor of store.index('docKey').iterate(docKey1)) {
      const token1 = cursor.value
      const token2 = await store.index('idByDoc').get([token1.id, docKey2])
      if (token2) {
        for (const segKey1 of token1.segKeys) {
          if (!candidates.has(segKey1)) candidates.set(segKey1, new Map())
          const candidates2 = candidates.get(segKey1)
          for (const segKey2 of token2.segKeys) {
            const count = (candidates2.get(segKey2) ?? 0) + 1
            candidates2.set(segKey2, count)
          }
        }
      }
    }
    return new Map([[[docKey1, docKey2], candidates]])
  }

  /**
   * Filter candidate pairs to get the most promising alignments.
   *
   * @param {Map} candidatesForDocPair - Candidate pairs with counts for a document pair.
   * @param {number} [topK=10] - Number of top candidates per segment.
   * @returns {Promise<Array>} Array of [[docKey1, segKey1], [docKey2, segKey2], score] tuples.
   */
  const filterTopCandidates = async (candidatesForDocPair, topK = 10) => {
    const scores = []
    const [[docKeys, candidates]] = candidatesForDocPair.entries()
    // Flatten nested objects.
    for (const [segKey1, candidates2] of candidates) {
      Array.from(candidates2.entries())
        .sort((a, b) => desc(a[1], b[1])) // sorts by count descending
        .slice(0, topK) // keeps only the top k candidates
        .map(async ([segKey2, score]) => {
          scores.push([[docKeys[0], segKey1], [docKeys[1], segKey2], score])
        })
    }
    return scores
  }

  /**
   * Greedily sort related alignments into groups and store them.
   *
   * @param {Array} scores - Array of candidate tuples, sorted by score.
   *   Expected format: [[docKey1, segKey1], [docKey2, segKey2], score]
   * @returns {Promise<void>} - Groups and scores have been saved.
   */
  const pickScores = async (scores) => {
    // Keep track of already aligned segments.
    const groupedSegs = await loadSegmentGroupMap()
    let tx = db.transaction('scores', 'readwrite')

    // Pick the best available pairing for unaligned segments.
    for (const candidate of scores) {
      const isValid = checkPairing(candidate, groupedSegs)
      if (isValid) {
        tx.store.add({
          docKeys: [candidate[0][0], candidate[1][0]].sort(asc),
          segKeys: [candidate[0][1], candidate[1][1]].sort(asc),
          score: candidate[2],
        })
      }
    }
    await tx.done

    // Save groups.
    return saveSegmentGroupMap(groupedSegs)
  }

  /**
   * Check if a pairing can be added to a group.
   *
   * @param {Array} candidate - A candidate tuple.
   *   Expected format: [[docKey1, segKey1], [docKey2, segKey2], score]
   * @param {Map} groupedSegs - A map of segments to groups.
   * @returns {bool} - True if the pairing was accepted.
   */
  const checkPairing = (candidate, groupedSegs) => {
    const [[docKey1, segKey1], [docKey2, segKey2], score] = candidate
    const group1 = groupedSegs.get(segKey1)?.group
    const group2 = groupedSegs.get(segKey2)?.group
    const addToGroup = (group, docKey, segKey) => {
      group.segments.set(docKey, segKey)
      groupedSegs.set(segKey, { ...groupedSegs.get(segKey), group, docKey })
    }
    if (!group1 && !group2) {
      const newGroup = { id: generateId(), segments: new Map() }
      addToGroup(newGroup, docKey1, segKey1)
      addToGroup(newGroup, docKey2, segKey2)
    } else if (group1 && !group2) {
      if (group1.segments.has(docKey2)) return false
      addToGroup(group1, docKey2, segKey2)
    } else if (!group1 && group2) {
      if (group2.segments.has(docKey1)) return false
      addToGroup(group2, docKey1, segKey1)
    } else if (group1 !== group2) {
      // Merge if no segments are from the same document.
      if (new Set(group1.segments.keys()).intersection(new Set(group2.segments.keys())).size)
        return false
      group2.segments.forEach((segKey, docKey) => {
        addToGroup(group1, docKey, segKey)
      })
    }
    return true
  }

  /**
   * Load existing groups from the store.
   *
   * @returns {Promise<Map>} - A map of groups keyed by segment key.
   */
  const loadSegmentGroupMap = async () => {
    const groupMap = new Map()
    const groups = new Map()
    const store = db.transaction('groups', 'readonly').store
    for await (const cursor of store) {
      const item = cursor.value
      if (!groups.has(item.id)) {
        groups.set(item.id, { id: item.id, segments: new Map([[item.docKey, item.segKey]]) })
      } else {
        groups.get(item.id).segments.set(item.docKey, item.segKey)
      }
      groupMap.set(item.segKey, { ...item, group: groups.get(item.id) })
    }
    return groupMap
  }

  /**
   * Save a map of groups in the store.
   *
   * @param {Map} groupedSegs - A map of groups keyed by segment key.
   * @returns {Promise<void>} - Groups have been saved.
   */
  const saveSegmentGroupMap = async (groupedSegs) => {
    const tx = db.transaction('groups', 'readwrite')
    groupedSegs.forEach((item, segKey) => {
      if (!item.key) {
        tx.store.add({
          id: item.group.id,
          docKey: item.docKey,
          segKey: segKey,
        })
      } else if (item.id !== item.group.id) {
        tx.store.put({
          key: item.key,
          id: item.group.id,
          docKey: item.docKey,
          segKey: segKey,
        })
      }
    })
    return tx.done
  }

  return {
    alignSegments,
    alignPair,
    findCandidates,
    filterTopCandidates,
    pickScores,
    checkPairing,
    loadSegmentGroupMap,
    saveSegmentGroupMap,
  }
}
