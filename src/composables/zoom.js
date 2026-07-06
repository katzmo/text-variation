import { usePinch, useWheel } from '@vueuse/gesture'
import { onKeyDown, useCssVar } from '@vueuse/core'

/**
 * A composable for managing zoom functionality in a Vue component.
 * Supports mouse wheel, keyboard shortcuts (Ctrl/Cmd + Arrow Up/Down), and touch gestures.
 *
 * @param {Object} wrapper - A ref object of the DOM element to zoom.
 * @param {Object} [options] - Configuration options for zoom behavior.
 * @param {number} [options.minZoom=0.1] - Minimum zoom level.
 * @param {number} [options.maxZoom=1.5] - Maximum zoom level.
 * @param {number} [options.zoomStep=0.05] - Increment/decrement step for zoom.
 * @returns {Object} An object containing zoom-related functions and reactive properties.
 */
export function useZoom(wrapper, options = {}) {
  const { minZoom = 0.1, maxZoom = 1.5, zoomStep = 0.05 } = options
  const currentZoom = useCssVar('--zoom-level', wrapper)

  /**
   * Increases the zoom level by the specified step.
   */
  const zoomIn = () => {
    if (currentZoom.value + zoomStep < maxZoom) {
      currentZoom.value += zoomStep
    }
  }

  /**
   * Decreases the zoom level by the specified step.
   */
  const zoomOut = () => {
    if (currentZoom.value - zoomStep > minZoom) {
      currentZoom.value -= zoomStep
    }
  }

  /**
   * Sets a custom zoom level.
   *
   * @param {number} level - The desired zoom level (must be between minZoom and maxZoom).
   */
  const setCustomZoom = (level) => {
    if (level >= minZoom && level <= maxZoom) {
      currentZoom.value = level
    }
  }

  /**
   * Handles mouse wheel events for zooming.
   *
   * @param {object} state - The gesture state object.
   */
  const handleWheel = (state) => {
    const {
      delta: [_, dy],
      ctrlKey,
      metaKey,
    } = state
    if (ctrlKey || metaKey) {
      dy < 0 ? zoomIn() : zoomOut()
    }
  }

  /**
   * Handles pinch touch events for zooming.
   *
   * @param {object} state - The gesture state object.
   */
  const handlePinch = (state) => {
    const {
      offset: [d],
    } = state
    d > 0 ? zoomIn() : zoomOut()
  }

  // Event listeners
  useWheel(handleWheel, { domTarget: wrapper })
  usePinch(handlePinch, { domTarget: wrapper, eventOptions: { passive: false } })
  onKeyDown((e) => (e.ctrlKey || e.metaKey) && e.key === 'ArrowUp', zoomIn)
  onKeyDown((e) => (e.ctrlKey || e.metaKey) && e.key === 'ArrowDown', zoomOut)

  return {
    currentZoom,
    zoomIn,
    zoomOut,
    setCustomZoom,
  }
}
