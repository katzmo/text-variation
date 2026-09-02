import { tokenize } from '@/utils/nlp'
import { useIndexedDBStore } from '@/composables/db'

/**
 * A composable for extracting data from documents to the DB.
 * @returns {Object} An object containing preprocessing functions.
 */
export function useDocumentProcessor() {
  const { db, dbExec } = useIndexedDBStore()

  /**
   * Process uploaded TEI files before saving them.
   *
   * @param {object} doc - A document object with XML content.
   * @returns {Document} - The parsed XML document.
   */
  const parseXML = (doc) => {
    const parser = new DOMParser()
    const xml = parser.parseFromString(doc.content, 'text/xml')
    // Read document ID.
    doc.id = xml.documentElement.getAttribute('xml:id') ?? doc.id
    return xml
  }

  /**
   * Find segments in XML.
   *
   * @param {Document} xml - Parsed XML document.
   * @param {object} doc - The document object related to the XML.
   * @param {string} [segmentSelector='head, p, lg, list'] - Selector for identifying segments.
   */
  const segmentXML = (xml, doc, segmentSelector = 'head, p, lg, list') => {
    const segments = xml.querySelector('body').querySelectorAll(segmentSelector)
    if (segments[0].hasAttribute('data-id')) return // Segments have already been parsed.
    for (const [index, seg] of segments.entries()) {
      let segId = `${doc.id}:${seg.tagName}:${index + 1}`
      seg.setAttribute('data-id', segId)
    }
    // Serialize back to XML string.
    doc.content = new XMLSerializer().serializeToString(xml)
  }

  /**
   * Extract text content from an element, skipping specified selectors.
   *
   * @param {Element} element - The DOM element to extract text from.
   * @param {string} [excludedSelector] - Selector for elements to exclude.
   *   Defaults to 'note, del, [rend~="strikethrough"], [rend~="linethrough"],
   *   [hidden], sic + corr, abbr + expan, orig + reg, span.reason'.
   * @returns {string} - The extracted text.
   */
  const getTextContent = (element, excludedSelector) => {
    excludedSelector ??=
      'note, del, [rend~="strikethrough"], [rend~="linethrough"], [hidden], sic + corr, abbr + expan, orig + reg, span.reason'
    const filteredEl = element.cloneNode(true)
    filteredEl.querySelectorAll(excludedSelector).forEach((ex) => ex.remove())
    return filteredEl.textContent.replace(/\s+/g, ' ')
  }

  /**
   * Save the text and tokens of each segment to the DB.
   *
   * @param {Document} xml - Parsed XML document with data-ids.
   * @param {object} doc - The document object related to the XML.
   */
  const saveSegments = async (xml, doc) => {
    const segments = xml.querySelectorAll('[data-id]')
    const tokens = {}
    for (const [index, seg] of segments.entries()) {
      const segId = seg.getAttribute('data-id')
      const data = await db.getFromIndex('segments', 'id', segId)
      if (data) break // assuming all segments have already been saved to the DB
      const content = getTextContent(seg)
      const segKey = await dbExec('segments', 'add', {
        docKey: doc.key,
        id: segId,
        pos: index + 1,
        content,
      })
      for (const token of tokenize(content)) {
        tokens[token] ??= []
        tokens[token].push(segKey)
      }
    }
    const tx = db.transaction('tokens', 'readwrite')
    await Promise.all(
      Object.entries(tokens).map(([id, segKeys]) => tx.store.add({ id, segKeys, docKey: doc.key })),
    )
    await tx.done
  }

  return {
    parseXML,
    segmentXML,
    getTextContent,
    saveSegments,
  }
}
