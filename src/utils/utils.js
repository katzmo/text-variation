/**
 * @module Utilities.
 * @description Helpers for text processing, similarity, etc.
 */

/**
 * Sort numbers ascending.
 *
 * @param {number} a - First number to compare.
 * @param {number} b - Second number to compare.
 * @returns {number} - Difference of both numbers.
 */
export function asc(a, b) {
  return a - b
}

/**
 * Sort numbers descending.
 *
 * @param {number} a - First number to compare.
 * @param {number} b - Second number to compare.
 * @returns {number} - Difference of both numbers.
 */
export function desc(a, b) {
  return b - a
}

/**
 * Generate a short random string.
 *
 * @param {int} [length=8] - The length of the output.
 * @returns {string} - A random base36 string.
 */
export function generateId(length = 8) {
  return Math.random()
    .toString(36)
    .substring(2, length + 2)
}

/**
 * Split a text into tokens on spaces and punctuation.
 *
 * @param {string} text - The text to split into tokens.
 * @returns {Set[string]} - A set of tokens.
 */
export function tokenize(text) {
  return new Set(text.match(/[^\p{P}\s]+/g)?.map((t) => t.toLowerCase()))
}
