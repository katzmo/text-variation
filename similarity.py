"""
similarity.py — interchangeable ways to score how similar two text units are.

Each function takes two "token bundles" (precomputed for speed) and returns a
number in [0, 1] where 1 = most similar. 
(order of words matters -> try Levenshtein / bigrams, not just Jaccard).

Build a bundle once per unit with make_bundle(text).
"""

from collections import Counter

class Bundle:
    """Precomputed tokens for one text unit, so we don't re-split repeatedly."""
    __slots__ = ("text", "words", "wset", "bigrams")

    def __init__(self, text):
        self.text = text
        self.words = text.split()
        self.wset = set(self.words)
        self.bigrams = set(zip(self.words, self.words[1:]))


def make_bundle(text):
    return Bundle(text)


def sim_jaccard(a, b):
    """Word-set overlap. Ignores order entirely. (Current production measure.)"""
    if not a.wset and not b.wset:
        return 1.0
    if not a.wset or not b.wset:
        return 0.0
    inter = len(a.wset & b.wset)
    return inter / (len(a.wset) + len(b.wset) - inter)


def sim_dice(a, b):
    """Sorensen-Dice on word sets. Like Jaccard but weights overlap more."""
    if not a.wset and not b.wset:
        return 1.0
    if not a.wset or not b.wset:
        return 0.0
    inter = len(a.wset & b.wset)
    return 2 * inter / (len(a.wset) + len(b.wset))


def sim_multi_dice(a, b):
    """Sorensen-Dice on all words."""
    if not a.words and not b.words:
        return 1.0
    if not a.words or not b.words:
        return 0.0
    inter = sum((Counter(a.words) & Counter(b.words)).values())
    return 2 * inter / (len(a.words) + len(b.words))


def sim_char_dice(a, b):
    """Sorensen-Dice on all characters."""
    if not a.text and not b.text:
        return 1.0
    if not a.text or not b.text:
        return 0.0
    inter = sum((Counter(a.text) & Counter(b.text)).values())
    return 2 * inter / (len(a.text) + len(b.text))


def sim_bigram_jaccard(a, b):
    """Jaccard on consecutive word pairs. Captures LOCAL word order cheaply."""
    if not a.bigrams and not b.bigrams:
        # fall back to unigram jaccard for very short lines
        return sim_jaccard(a, b)
    if not a.bigrams or not b.bigrams:
        return 0.0
    inter = len(a.bigrams & b.bigrams)
    return inter / (len(a.bigrams | b.bigrams))


_MAX_LEV_WORDS = 300  # guard against parsing artifacts (e.g. last <lb/> capturing entire page)

def sim_word_levenshtein(a, b):
    """
    Word-level edit distance, normalised to a similarity in [0, 1].
    Fully respects word ORDER (insertions, deletions, substitutions).
    Heavier than Jaccard, so best on lines / small sections.
    Falls back to Jaccard when either unit exceeds _MAX_LEV_WORDS (parsing artifacts).
    """
    wa, wb = a.words, b.words
    m, n = len(wa), len(wb)
    if m == 0 and n == 0:
        return 1.0
    if m == 0 or n == 0:
        return 0.0
    if m > _MAX_LEV_WORDS or n > _MAX_LEV_WORDS:
        return sim_jaccard(a, b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        wai = wa[i - 1]
        for j in range(1, n + 1):
            cost = 0 if wai == wb[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return 1 - prev[n] / max(m, n)


def sim_char_levenshtein(a, b):
    """Character-level edit distance, normalised to a similarity in [0, 1]."""
    ta, tb = a.text, b.text
    m, n = len(ta), len(tb)
    if m == 0 and n == 0:
        return 1.0
    if m == 0 or n == 0:
        return 0.0
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        wai = ta[i - 1]
        for j in range(1, n + 1):
            cost = 0 if wai == tb[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return 1 - prev[n] / max(m, n)


def make_combined(w_jaccard=0.5, w_lev=0.5):
    """Weighted blend of Jaccard (set overlap) and word-Levenshtein (order)."""
    def sim(a, b):
        return w_jaccard * sim_jaccard(a, b) + w_lev * sim_word_levenshtein(a, b)
    sim.__name__ = f"combined(j={w_jaccard},lev={w_lev})"
    return sim


# Registry so configs can name a measure as a string.
SIMILARITIES = {
    "jaccard": sim_jaccard,
    "dice": sim_dice,
    "dice-all": sim_multi_dice,
    "dice-char": sim_char_dice,
    "bigram": sim_bigram_jaccard,
    "levenshtein": sim_word_levenshtein,
    "levenshtein-char": sim_char_levenshtein,
    "combined": make_combined(0.5, 0.5),
}
