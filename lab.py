#!/usr/bin/env python3
"""
lab.py — experiment with alignment without touching the production tool.

QUICK START
-----------
  python lab.py                     # compare all configs on the sample pair
  python lab.py --list              # list the named configs
  python lab.py --config sections5  # run one config, show sample matches
  python lab.py --all-pairs         # every text as anchor (Katharina #2)
  python lab.py --data path/to/dir  # point at your own folder of .xml files

Drop more TEI files into ./data (or pass --data) to test on a bigger corpus.

WHAT EACH KNOB MAPS TO (Katharina's notes)
  #1 larger sections   -> "window" (1 = lines, 5/10 = merged sections)
  #2 every text anchor -> --all-pairs
  #3 experiment algo   -> "strategy": lis | nw
  #4 similar position  -> "band_frac" (hard band) / "pos_weight" (soft prior)
  #5 order matters     -> "similarity": jaccard | dice | bigram | levenshtein | combined
"""
import argparse
import sys
import time
from pathlib import Path

import parsers
import similarity
import strategies
import evaluate

HERE = Path(__file__).parent
DEFAULT_DATA = HERE / "data"


# Named experiment configurations. Add your own freely.
CONFIGS = {
    # baseline = current production behaviour
    "baseline":      dict(window=1,  similarity="jaccard",     strategy="lis"),
    # #1 larger sections
    "sections5":     dict(window=5,  similarity="jaccard",     strategy="lis"),
    "sections10":    dict(window=10, similarity="jaccard",     strategy="lis"),
    # #5 order-aware word similarity
    "dice":          dict(window=1,  similarity="dice",        strategy="lis"),
    "dice-all":      dict(window=1,  similarity="dice-all",    strategy="lis"),
    "bigram":        dict(window=1,  similarity="bigram",      strategy="lis"),
    "levenshtein":   dict(window=1,  similarity="levenshtein", strategy="lis"),
    "combined":      dict(window=1,  similarity="combined",    strategy="lis"),
    # #6 order-aware character similarity
    "dice-char":      dict(window=1,  similarity="dice-char",  strategy="lis"),
    "levenshtein-char": dict(window=1, similarity="levenshtein-char", strategy="lis"),
    # #4 positional preference
    "banded":        dict(window=1,  similarity="jaccard",     strategy="lis", band_frac=0.15),
    "positional":    dict(window=1,  similarity="jaccard",     strategy="lis", pos_weight=0.3),
    # #3 different algorithm
    "nw":            dict(window=1,  similarity="jaccard",     strategy="nw"),
    # a promising blend to try
    "sections5_lev": dict(window=5,  similarity="levenshtein", strategy="lis"),
}

COMMON = dict(threshold=0.1, top_k=5, min_word_len=3, pos_weight=0.01)


def load_corpus(data_dir, tags_str):
    files = sorted(Path(data_dir).glob("*.xml"))
    if not files:
        sys.exit(f"No .xml files in {data_dir}. Drop some TEI files there.")
    tags = [tag.strip() for tag in tags_str.split(",")]
    corpus = {}
    for f in files:
        xml_id, segments = parsers.load_segments(f, tags)
        # clean id = xml:id or filename prefix before first dash/dot
        wid = xml_id or f.stem.split("-")[0].split(".")[0]
        corpus[wid] = segments
        print(f"  loaded {wid}: {len(segments)} segments", file=sys.stderr)
    return corpus


def prepare(lines, window):
    units = parsers.group_units(lines, window)
    bundles = [similarity.make_bundle(u["text"]) for u in units]
    return units, bundles


def run_one(cfg, wit_lines, anc_lines):
    """Run one config on one (witness, anchor) pair. Returns (alignment, units, secs)."""
    window = cfg.get("window", 1)
    sim_fn = similarity.SIMILARITIES[cfg["similarity"]]
    strat = strategies.STRATEGIES[cfg["strategy"]]
    wit_units, wit_b = prepare(wit_lines, window)
    anc_units, anc_b = prepare(anc_lines, window)
    opts = dict(COMMON)
    for k in ("band_frac", "pos_weight", "gap"):
        if k in cfg:
            opts[k] = cfg[k]
    t0 = time.time()
    alignment = strat(wit_units, anc_units, wit_b, anc_b, sim_fn, **opts)
    secs = time.time() - t0
    return alignment, wit_units, anc_units, secs


def cmd_compare(corpus, names, samples):
    ids = list(corpus)
    # anchor = longest witness; witness = next longest, for an informative rate
    by_len = sorted(ids, key=lambda i: -len(corpus[i]))
    anchor_id = by_len[0]
    wit_id = by_len[1] if len(by_len) > 1 else by_len[0]
    print(f"\nComparing configs   witness={wit_id}  anchor={anchor_id}\n")

    rows = []
    stored = {}
    for name in names:
        cfg = CONFIGS[name]
        al, wu, au, secs = run_one(cfg, corpus[wit_id], corpus[anchor_id])
        m = evaluate.metrics(al, len(au))
        stored[name] = (al, wu, au)
        rows.append([
            name,
            f"{m['rate']*100:.1f}%",
            m["aligned"],
            f"{m['mean_score']:.3f}",
            f"{m['monotonic']:.2f}",
            f"{m['anchor_cov']*100:.1f}%",
            f"{secs:.2f}s",
        ])
    evaluate.print_table(
        rows,
        ["config", "rate", "aligned", "mean_sc", "mono", "anc_cov", "time"],
    )

    # agreement of every config vs the baseline (where both align, do they agree?)
    if "baseline" in stored:
        print("\nAgreement with baseline (same target where both align):")
        base_al = stored["baseline"][0]
        ag_rows = []
        for name in names:
            if name == "baseline":
                continue
            ag = evaluate.agreement(stored[name][0], base_al)
            ag_rows.append([name, "n/a" if ag is None else f"{ag*100:.0f}%"])
        evaluate.print_table(ag_rows, ["config", "agree"])

    # sample matches for the first requested config (eyeball quality)
    show = names[0]
    al, wu, au = stored[show]
    print(f"\nSample matches for '{show}' (score | witness text | anchor text):")
    for sc, wt, at in evaluate.sample_matches(al, wu, au, k=samples):
        print(f"  {sc:.3f}  {wt[:46]:46}  |  {at[:46]}")


def cmd_all_pairs(corpus, cfg_name):
    cfg = CONFIGS[cfg_name]
    ids = list(corpus)
    print(f"\nAll-pairs alignment rate (rows=witness, cols=anchor)   config={cfg_name}\n")
    header = ["wit \\ anc"] + ids
    rows = []
    for wid in ids:
        row = [wid]
        for aid in ids:
            if wid == aid:
                row.append("--")
                continue
            al, wu, au, _secs = run_one(cfg, corpus[wid], corpus[aid])
            m = evaluate.metrics(al, len(au))
            row.append(f"{m['rate']*100:.0f}%")
        rows.append(row)
    evaluate.print_table(rows, header)
    print("\nTip: a good anchor is one that many witnesses align to well (a dense column).")


def main():
    ap = argparse.ArgumentParser(description="Alignment experimentation harness")
    ap.add_argument("--data", default=str(DEFAULT_DATA), help="folder of .xml TEI files")
    ap.add_argument("--tags", default="p,lg", help="tags to use as segments")
    ap.add_argument("--config", help="run a single named config")
    ap.add_argument("--all-pairs", action="store_true", help="every text as anchor")
    ap.add_argument("--list", action="store_true", help="list configs and exit")
    ap.add_argument("--samples", type=int, default=8, help="sample matches to print")
    args = ap.parse_args()

    if args.list:
        print("Available configs:")
        for name, cfg in CONFIGS.items():
            print(f"  {name:16} {cfg}")
        return

    print("Loading corpus...", file=sys.stderr)
    corpus = load_corpus(args.data, args.tags)

    if args.all_pairs:
        cmd_all_pairs(corpus, args.config or "baseline")
    elif args.config:
        cmd_compare(corpus, [args.config], args.samples)
    else:
        cmd_compare(corpus, list(CONFIGS), args.samples)


if __name__ == "__main__":
    main()
