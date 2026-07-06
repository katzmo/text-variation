"""
strategies.py — interchangeable alignment algorithms.

Every strategy has the same signature and returns the same shape, so the
harness can swap them freely:

    strategy(wit_units, anc_units, wit_bundles, anc_bundles, sim_fn, **opts)
      -> list of records, one per witness unit:
         {"wit_idx": i, "anc_idx": j or None, "score": float}

Implemented:
  two_pass_lis  - the current production approach (inverted index + best match
                  above threshold, then Longest Increasing Subsequence to keep
                  matches in reading order). Supports an optional positional
                  prior and a search band (Katharina's point #4).
  needleman_wunsch - classic global alignment with gaps, banded for speed,
                  order-preserving by construction (Katharina's point #3).

Both take a `sim_fn` from similarity.py.
"""
from bisect import bisect_left


# ---------------------------------------------------------------- helpers
def _build_index(bundles, min_word_len=3):
    """word -> [anchor positions], for fast candidate lookup."""
    idx = {}
    for pos, b in enumerate(bundles):
        for w in b.wset:
            if len(w) > min_word_len:
                idx.setdefault(w, []).append(pos)
    return idx


def _lis(matches):
    """
    matches: list of (wit_idx, anc_idx, score) already sorted by wit_idx.
    Returns the longest subsequence with strictly increasing anc_idx
    (patience sorting, O(n log n)).
    """
    if not matches:
        return []
    tails, tail_i, parent = [], [], [-1] * len(matches)
    for i, (_wi, ap, _sc) in enumerate(matches):
        j = bisect_left(tails, ap)
        if j == len(tails):
            tails.append(ap)
            tail_i.append(i)
        else:
            tails[j] = ap
            tail_i[j] = i
        parent[i] = tail_i[j - 1] if j > 0 else -1
    path, cur = [], tail_i[-1]
    while cur != -1:
        path.append(matches[cur])
        cur = parent[cur]
    path.reverse()
    return path


# ---------------------------------------------------------------- strategy 1
def two_pass_lis(wit_units, anc_units, wit_b, anc_b, sim_fn,
                 threshold=0.35, top_k=15, min_word_len=3,
                 band_frac=None, pos_weight=0.0):
    """
    Production-style two-pass alignment, with two optional extras:
      band_frac : if set (e.g. 0.15), only consider anchor positions within
                  +/- band_frac * len(anchor) of the proportional expected
                  position. Implements 'prefer similar position' as a hard band.
      pos_weight: if > 0, subtract pos_weight * |relative position gap| from
                  each candidate score. A soft positional prior.
    """
    anc_idx = _build_index(anc_b, min_word_len)
    A = len(anc_units)
    W = len(wit_units)
    band = int(band_frac * A) if band_frac else None

    # Find most promising candidates (= most overlapping words)
    # and calculate their similarity scores
    raw = []
    for wi in range(W):
        wb = wit_b[wi]
        expected = (wi / W) * A if W else 0
        cands = {}
        for w in wb.words:
            if len(w) > min_word_len:
                for pos in anc_idx.get(w, ()):
                    if band is not None and abs(pos - expected) > band:
                        continue
                    cands[pos] = cands.get(pos, 0) + 1
        if not cands:
            continue
        top = sorted(cands.items(), key=lambda x: -x[1])[:top_k]
        for pos, _ in top:
            score = sim_fn(wb, anc_b[pos])
            if pos_weight and A:
                score -= pos_weight * abs(pos - expected) / A
            if score >= threshold:
                raw.append((wi, pos, score))

    # Return the highest scoring pairings found.
    raw.sort(key=lambda x: -x[2]) # sort by score
    used_wit_indices = set()
    used_anc_indices = set()
    out = [{'wit_idx': wi, 'anc_idx': None, 'score': 0.0} for wi in range(W)]

    for wit_idx, anc_idx, score in raw:
        if wit_idx not in used_wit_indices and anc_idx not in used_anc_indices:
            out[wit_idx] = {'wit_idx': wit_idx, 'anc_idx': anc_idx, 'score': round(score, 4)}
            used_wit_indices.add(wit_idx)
            used_anc_indices.add(anc_idx)
    return out


# ---------------------------------------------------------------- strategy 2
def needleman_wunsch(wit_units, anc_units, wit_b, anc_b, sim_fn,
                     threshold=0.35, gap=-0.4, band_frac=0.12, **_):
    """
    Global alignment maximising total similarity, with a gap penalty.
    Banded around the proportional diagonal for speed (full NW would be huge).
    Order-preserving by construction. A unit counts as 'aligned' if its matched
    similarity clears `threshold`.
    """
    W, A = len(wit_units), len(anc_units)
    if W == 0 or A == 0:
        return [{"wit_idx": i, "anc_idx": None, "score": 0.0} for i in range(W)]
    ratio = A / W
    band = max(20, int(band_frac * max(W, A)))

    NEG = float("-inf")
    # score[i][j] over a band; store as dicts per row to stay sparse
    score = [dict() for _ in range(W + 1)]
    back = [dict() for _ in range(W + 1)]
    score[0][0] = 0.0

    def jrange(i):
        center = int(i * ratio)
        lo = max(0, center - band)
        hi = min(A, center + band)
        return lo, hi

    for i in range(0, W + 1):
        lo, hi = (0, 0) if i == 0 else jrange(i)
        for j in range(lo, hi + 1):
            best, move = NEG, None
            # gap in anchor (consume witness unit i, no anchor)
            if (j) in score[i - 1] if i > 0 else False:
                v = score[i - 1][j] + gap
                if v > best:
                    best, move = v, ("up", None)
            # gap in witness (consume anchor unit j)
            if i >= 0 and (j - 1) in score[i] and j > 0:
                v = score[i][j - 1] + gap
                if v > best:
                    best, move = v, ("left", None)
            # match/substitute
            if i > 0 and j > 0 and (j - 1) in score[i - 1]:
                s = sim_fn(wit_b[i - 1], anc_b[j - 1])
                v = score[i - 1][j - 1] + s
                if v > best:
                    best, move = v, ("diag", (j - 1, s))
            if i == 0 and j == 0:
                continue
            if move is not None:
                score[i][j] = best
                back[i][j] = move

    # traceback from the best cell in the last row
    if not score[W]:
        return [{"wit_idx": i, "anc_idx": None, "score": 0.0} for i in range(W)]
    jbest = max(score[W], key=lambda j: score[W][j])
    matched = {}
    i, j = W, jbest
    while i > 0 or j > 0:
        if i not in range(len(back)) or j not in back[i]:
            break
        move, payload = back[i][j]
        if move == "diag":
            anc_j, s = payload
            matched[i - 1] = (anc_j, s)
            i, j = i - 1, j - 1
        elif move == "up":
            i = i - 1
        else:
            j = j - 1

    out = []
    for wi in range(W):
        if wi in matched and matched[wi][1] >= threshold:
            ap, sc = matched[wi]
            out.append({"wit_idx": wi, "anc_idx": ap, "score": round(sc, 4)})
        else:
            out.append({"wit_idx": wi, "anc_idx": None, "score": 0.0})
    return out


STRATEGIES = {
    "lis": two_pass_lis,
    "nw": needleman_wunsch,
}
