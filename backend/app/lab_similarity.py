"""
lab_similarity.py — similarity functions ported verbatim from the
align-lab experiment (Katharina thesis), kept self-contained so the
running app never depends on paths outside this repo.

Source: Katharina thesis/align-lab/similarity.py
  - Bundle, sim_dice                 -> Dice ("all") alignment scoring
  - sim_jaccard, sim_word_levenshtein, hybrid_score (="combined") -> pairwise scoring
"""


class Bundle:
    """Precomputed tokens for one text unit, so we don't re-split repeatedly."""
    __slots__ = ("words", "wset", "bigrams", "text")

    def __init__(self, text):
        self.text = text
        self.words = text.split()
        self.wset = set(self.words)
        self.bigrams = set(zip(self.words, self.words[1:]))


def sim_dice(a, b):
    """Sorensen-Dice on word sets. Like Jaccard but weights overlap more."""
    if not a.wset and not b.wset:
        return 1.0
    if not a.wset or not b.wset:
        return 0.0
    inter = len(a.wset & b.wset)
    return 2 * inter / (len(a.wset) + len(b.wset))


def sim_jaccard(a, b):
    """Word-set overlap. Ignores order entirely."""
    if not a.wset and not b.wset:
        return 1.0
    if not a.wset or not b.wset:
        return 0.0
    inter = len(a.wset & b.wset)
    return inter / (len(a.wset) + len(b.wset) - inter)


_MAX_LEV_WORDS = 300  # guard against parsing artifacts


def sim_word_levenshtein(a, b):
    """Word-level edit distance, normalised to a similarity in [0, 1]."""
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


def hybrid_score(a, b):
    """Hybrid Levenshtein pair-scorer: 0.5*jaccard + 0.5*word-Levenshtein
    (= "combined" in align-lab/similarity.py, weights 0.5/0.5)."""
    return 0.5 * sim_jaccard(a, b) + 0.5 * sim_word_levenshtein(a, b)
