"""
evaluate.py — turn an alignment into comparable numbers, and compare configs.

Important honesty note: without a hand-made gold standard, a HIGHER alignment
rate is NOT automatically "better" (it could mean more false matches). So we
report several proxy metrics and also print sample matches for eyeballing, plus
a cross-config AGREEMENT score: where two different methods both align a line,
do they agree on the target? High agreement on high-score matches is a good
sign that both are finding real correspondences.
"""
from statistics import mean, median


def metrics(alignment, n_anchor):
    aligned = [r for r in alignment if r["anc_idx"] is not None]
    n = len(alignment)
    n_al = len(aligned)
    scores = [r["score"] for r in aligned]
    # monotonicity: among aligned (in witness order), fraction strictly increasing
    mono = 1.0
    if len(aligned) > 1:
        inc = sum(
            1 for a, b in zip(aligned, aligned[1:]) if b["anc_idx"] > a["anc_idx"]
        )
        mono = inc / (len(aligned) - 1)
    coverage = len({r["anc_idx"] for r in aligned}) / n_anchor if n_anchor else 0.0
    return {
        "units": n,
        "aligned": n_al,
        "rate": n_al / n if n else 0.0,
        "mean_score": mean(scores) if scores else 0.0,
        "median_score": median(scores) if scores else 0.0,
        "monotonic": mono,
        "anchor_cov": coverage,
    }


def agreement(a, b):
    """
    Fraction of witness units aligned by BOTH a and b that map to the same
    anchor unit. Measures how much two methods agree where they overlap.
    """
    bmap = {r["wit_idx"]: r["anc_idx"] for r in b if r["anc_idx"] is not None}
    both = same = 0
    for r in a:
        if r["anc_idx"] is not None and r["wit_idx"] in bmap:
            both += 1
            if bmap[r["wit_idx"]] == r["anc_idx"]:
                same += 1
    return same / both if both else None


def sample_matches(alignment, wit_units, anc_units, k=6, min_score=0.0):
    """Return up to k aligned pairs (highest score first) for manual inspection."""
    aligned = [r for r in alignment if r["anc_idx"] is not None and r["score"] >= min_score]
    aligned.sort(key=lambda r: -r["score"])
    rows = []
    for r in aligned[:k]:
        wu = wit_units[r["wit_idx"]]
        au = anc_units[r["anc_idx"]]
        rows.append((r["score"], wu["text"], au["text"]))
    return rows


def print_table(rows, headers):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(str(c)))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))
