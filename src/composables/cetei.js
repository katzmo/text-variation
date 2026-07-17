import { onMounted, ref } from 'vue'

import CETEI from 'CETEIcean'

const CETEIcean = ref(new CETEI({ ignoreFragmentId: true }))
CETEIcean.value.addBehaviors({
  tei: {
    // Display document ID
    TEI: (el) => {
      const xmlId = el.getAttribute('xml:id')
      if (xmlId) {
        el.insertAdjacentHTML('afterbegin', `<div class="identifier">${xmlId}</div>`)
      }
    },
    // Render line breaks
    lb: ['<br>'],
    // Display a reason in gaps
    gap: ['<span class="reason">$@reason</span>'],
    // Display header information
    teiHeader: null,
  },
})

/**
 * A composable for sharing a CETEI instance.
 *
 * @returns An object containing the CETEI instance and utility functions.
 */
export function useCETEI() {
  /**
   * Converts TEI to HMTL and appends it to a wrapper.
   *
   * @param {object} wrapper - A reference to a wrapper element.
   * @param {string} xmlString - The XML string to convert into HTML.
   */
  const appendXmlString = (wrapper, xmlString) => {
    onMounted(() => {
      console.log(wrapper.value)
      CETEIcean.value.makeHTML5(xmlString, (data) => {
        wrapper.value.appendChild(data)
      })
    })
  }
  return { CETEIcean, appendXmlString }
}
