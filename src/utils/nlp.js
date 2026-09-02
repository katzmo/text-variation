/**
 * @module NLP utils
 * @description Utility functions for text processing.
 */

/**
 * Split a text into tokens (using word bounderies).
 *
 * @param {string} text - The text to split into tokens.
 * @returns {Array[string]} - An array of tokens.
 */
export function tokenize(text) {
  return new Set(text.match(/\w+/g).map((t) => t.toLowerCase()))
}
