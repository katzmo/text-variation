import { ref } from 'vue'

/**
 * A composable for managing aligned groups in a Vue component.
 *
 * @param {Object} wrapper - A ref object of the DOM element containing matched sequences.
 * @param {Object} [options] - Configuration options for alignment behavior.
 * @param {number} [options.alignedClass='aligned'] - Class to set when a group is aligned.
 * @param {number} [options.highlightedClass='highlighted'] - Class to set when a group is highlighted.
 * @returns {Object} An object containing alignment-related functions and reactive properties.
 */
export function useAlignment(wrapper, options = {}) {
  const { alignedClass = 'aligned', highlightedClass = 'highlighted' } = options

  /*
   * Reactive storage for the currently selected group.
   */
  const alignedGroupId = ref()

  /**
   * Align elements by pushing their parents down.
   *
   * @param {string} selector - Selector matching elements to align.
   * @param {string} parentSelector - Selector of parents where the margin is set.
   * @param {float} [zoomValue=1] - Adjust margins to an outer zoom level.
   * @param {boolean} [isNew=true] - Whether it's a new alignment or update.
   */
  const alignSections = (selector, parentSelector, zoomValue = 1, isNew = true) => {
    const sections = wrapper.value.querySelectorAll(selector)
    if (isNew) {
      wrapper.value.querySelectorAll(`.${alignedClass}`).forEach((el) => {
        el.classList.remove(alignedClass)
      })
      sections.forEach((el) => {
        el.classList.add(alignedClass)
      })
    }
    const maxOffsetTop = Math.max(...[...sections].map((el) => el.offsetTop))
    sections.forEach((el) => {
      const marginTop = (maxOffsetTop - el.offsetTop) * zoomValue
      el.closest(parentSelector).style.marginTop = marginTop + 'px'
    })
    sections[0].scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }

  /**
   * Add the highlighted class on all section elements matching the selector.
   *
   * @param {string} selector - A selector for section elements.
   */
  const highlightSections = (selector) => {
    const sections = wrapper.value.querySelectorAll(selector)
    sections.forEach((el) => {
      el.classList.add(highlightedClass)
    })
  }

  /**
   * Remove the highlighted class on all section elements matching the selector.
   *
   * @param {string} selector - A selector for section elements.
   */
  const unhighlightSections = (selector) => {
    const sections = wrapper.value.querySelectorAll(selector)
    sections.forEach((el) => {
      el.classList.remove(highlightedClass)
    })
  }

  return { alignedGroupId, alignSections, highlightSections, unhighlightSections }
}
