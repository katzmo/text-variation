/**
 * @module Utilities.
 * @description Helpers for text processing, similarity, etc.
 */

/**
 * Split a text into tokens on spaces and punctuation.
 *
 * @param {string} text - The text to split into tokens.
 * @returns {Set[string]} - A set of tokens.
 */
export function tokenize(text) {
  return new Set(text.match(/[^\p{P}\s]+/g)?.map((t) => t.toLowerCase()))
}
