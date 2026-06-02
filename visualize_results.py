#!/usr/bin/env python3
"""
visualize_results.py — parse results_all.txt and produce comparison plots.

Plots produced:
  plot_config_comparison.png  — bar chart: all single-anchor configs
  plot_allpairs_heatmap.png   — heatmap of all-pairs alignment rate matrix
  plot_similarity_measures.png — grouped bar: similarity measures compared
  plot_section_size.png       — line chart: section size effect

Also prints a summary table to stdout.
"""

import re
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

RESULTS_FILE = Path("results_all.txt")

# ──────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────────────────────────────────────

def _pct(s):
    """'73.4%' -> 73.4, or '--' -> NaN"""
    s = str(s).strip()
    if s in ("--", "n/a", ""):
        return float("nan")
    return float(s.rstrip("%"))


def parse_config_comparison_blocks(text):
    """
    Find every 'config comparison' table in the text.
    Returns a list of dicts with keys:
      config, rate, aligned, mean_sc, mono, anc_cov, time, witness, anchor
    """
    rows = []

    # Detect which witness/anchor pair each block refers to
    pair_re = re.compile(
        r"Comparing configs\s+witness=(\S+)\s+anchor=(\S+)", re.IGNORECASE
    )
    block_re = re.compile(
        r"Comparing configs.*?(?=Comparing configs|\Z)", re.DOTALL
    )

    for block in block_re.finditer(text):
        block_text = block.group()
        m = pair_re.search(block_text)
        witness = m.group(1) if m else "?"
        anchor = m.group(2) if m else "?"

        # Table starts after the header line "config  rate  aligned ..."
        # and ends at a blank line or "Agreement" or "Sample"
        table_re = re.compile(
            r"^config\s+rate\s+aligned.*?\n"   # header
            r"[-\s]+\n"                         # separator
            r"(.*?)(?=\n\n|\nAgreement|\nSample|\Z)",
            re.DOTALL | re.MULTILINE,
        )
        tm = table_re.search(block_text)
        if not tm:
            continue
        for line in tm.group(1).splitlines():
            parts = line.split()
            if len(parts) < 6:
                continue
            # columns: config rate aligned mean_sc mono anc_cov [time]
            try:
                rows.append({
                    "config":   parts[0],
                    "rate":     _pct(parts[1]),
                    "aligned":  int(parts[2]),
                    "mean_sc":  float(parts[3]),
                    "mono":     float(parts[4]),
                    "anc_cov":  _pct(parts[5]),
                    "time":     parts[6] if len(parts) > 6 else "",
                    "witness":  witness,
                    "anchor":   anchor,
                })
            except (ValueError, IndexError):
                pass
    return rows


def _col_spans_from_sep(sep_line):
    """
    Given a separator line of form '-----  -----  -----  ...',
    return list of (start, end) byte positions for each column.
    print_table uses exactly 2-space gaps between dash-segments.
    """
    spans = []
    i = 0
    n = len(sep_line)
    while i < n:
        if sep_line[i] == "-":
            start = i
            while i < n and sep_line[i] == "-":
                i += 1
            spans.append((start, i))
        else:
            i += 1
    return spans


def _extract_cols(line, spans):
    """Slice `line` at each (start, end) span; strip whitespace."""
    result = []
    for start, end in spans:
        result.append(line[start:end].strip() if start < len(line) else "")
    return result


def parse_allpairs_blocks(text):
    """
    Find all-pairs tables. Returns dict cfg_name -> DataFrame.
    Uses fixed-width column parsing (via separator line) to handle
    multi-word witness IDs like 'LONDON OR5260' and 'OX E'.
    """
    blocks = re.split(r"All-pairs alignment rate.*?config=(\S+)", text)
    dfs = {}
    i = 1
    while i < len(blocks) - 1:
        cfg_name = blocks[i].strip()
        table_text = blocks[i + 1]
        i += 2

        # Work with the raw (non-stripped) lines to preserve column positions
        raw_lines = table_text.splitlines()
        header_idx = None
        for li, l in enumerate(raw_lines):
            if re.match(r"wit\s*\\?\s*anc", l, re.IGNORECASE):
                header_idx = li
                break
        if header_idx is None:
            continue

        # The separator line immediately follows the header
        sep_idx = header_idx + 1
        if sep_idx >= len(raw_lines):
            continue
        sep_line = raw_lines[sep_idx]

        # Determine fixed column positions from dash segments
        spans = _col_spans_from_sep(sep_line)
        if len(spans) < 2:
            continue

        # Extract anchor IDs from header using column positions
        # spans[0] is the row-label column; spans[1:] are anchor columns
        header_line = raw_lines[header_idx]
        anchor_ids = [_extract_cols(header_line, [s])[0] for s in spans[1:]]

        # Parse data rows
        matrix_rows = {}
        for l in raw_lines[sep_idx + 1:]:
            if not l.strip() or l.strip().startswith("Tip"):
                break
            cells = _extract_cols(l, spans)
            if not cells:
                continue
            wid = cells[0]
            if not wid:
                continue
            vals = []
            for cell in cells[1:]:
                if cell in ("--", ""):
                    vals.append(float("nan"))
                else:
                    try:
                        vals.append(float(cell.rstrip("%")))
                    except ValueError:
                        vals.append(float("nan"))
            matrix_rows[wid] = vals

        if matrix_rows and anchor_ids:
            n_cols = len(anchor_ids)
            trimmed = {k: v[:n_cols] for k, v in matrix_rows.items() if v}
            if trimmed:
                df = pd.DataFrame.from_dict(trimmed, orient="index",
                                            columns=anchor_ids)
                dfs[cfg_name] = df
    return dfs


# ──────────────────────────────────────────────────────────────────────────────
# Plot helpers
# ──────────────────────────────────────────────────────────────────────────────

PALETTE = ["#2166ac", "#4dac26", "#d01c8b", "#f1a340", "#762a83",
           "#1b7837", "#e66101", "#5aae61", "#b2abd2", "#008837"]

def _bar_chart(ax, categories, values1, values2, label1, label2, title, ylabel):
    x = np.arange(len(categories))
    w = 0.35
    b1 = ax.bar(x - w / 2, values1, w, label=label1, color=PALETTE[0],
                edgecolor="white", linewidth=0.5)
    b2 = ax.bar(x + w / 2, values2, w, label=label2, color=PALETTE[1],
                edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    # value labels
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        if not np.isnan(h):
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                    f"{h:.1f}", ha="center", va="bottom", fontsize=7)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    if not RESULTS_FILE.exists():
        sys.exit(f"ERROR: {RESULTS_FILE} not found. Run the experiments first.")

    text = RESULTS_FILE.read_text(encoding="utf-8", errors="replace")

    # ── Parse config comparison rows ──────────────────────────────────────────
    comp_rows = parse_config_comparison_blocks(text)
    if not comp_rows:
        print("WARNING: No config-comparison table rows found in results_all.txt.")
    df_comp = pd.DataFrame(comp_rows) if comp_rows else pd.DataFrame()

    # ── Parse all-pairs matrices ──────────────────────────────────────────────
    ap_dfs = parse_allpairs_blocks(text)

    # ──────────────────────────────────────────────────────────────────────────
    # Plot 1: config comparison (all single-anchor configs)
    # ──────────────────────────────────────────────────────────────────────────
    SINGLE_CONFIGS = [
        "baseline", "dice", "levenshtein", "combined",
        "sections5", "sections10", "positional", "banded",
    ]

    fig, ax = plt.subplots(figsize=(11, 5))

    if not df_comp.empty:
        # Use first occurrence of each config (the all-configs run)
        first_run = df_comp.drop_duplicates("config", keep="first")
        plot_df = first_run[first_run["config"].isin(SINGLE_CONFIGS)].copy()
        plot_df = plot_df.set_index("config").reindex(
            [c for c in SINGLE_CONFIGS if c in plot_df.index]
        )
        cats = plot_df.index.tolist()
        rates = plot_df["rate"].fillna(0).tolist()
        scores = [v * 100 for v in plot_df["mean_sc"].fillna(0).tolist()]
        _bar_chart(ax, cats, rates, scores,
                   "Alignment rate (%)", "Mean score (×100)",
                   "Config comparison — alignment rate vs mean score",
                   "Value")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Config comparison")

    fig.tight_layout()
    fig.savefig("plot_config_comparison.png", dpi=150)
    plt.close(fig)
    print("Saved plot_config_comparison.png")

    # ──────────────────────────────────────────────────────────────────────────
    # Plot 2: all-pairs heatmap
    # ──────────────────────────────────────────────────────────────────────────
    fig2, ax2 = plt.subplots(figsize=(14, 11))

    ap_df = None
    if ap_dfs:
        # prefer baseline; otherwise first available
        ap_df = ap_dfs.get("baseline")
        if ap_df is None:
            ap_df = next(iter(ap_dfs.values()))

    if ap_df is not None and not ap_df.empty:
        # Ensure numeric
        ap_num = ap_df.apply(pd.to_numeric, errors="coerce")
        # Trim to square if needed
        ids = [c for c in ap_num.index if c in ap_num.columns]
        # use all rows/cols we have
        mask = np.isnan(ap_num.values.astype(float))
        im = ax2.imshow(ap_num.values.astype(float), aspect="auto",
                        cmap="YlOrRd", vmin=0, vmax=100, interpolation="nearest")
        ax2.set_xticks(range(len(ap_num.columns)))
        ax2.set_xticklabels(ap_num.columns.tolist(), rotation=45, ha="right", fontsize=7)
        ax2.set_yticks(range(len(ap_num.index)))
        ax2.set_yticklabels(ap_num.index.tolist(), fontsize=7)
        plt.colorbar(im, ax=ax2, label="Alignment rate (%)", shrink=0.7)
        ax2.set_title("All-pairs alignment rate (row=witness, col=anchor)\n"
                      "Darker = more lines aligned", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Anchor witness", fontsize=10)
        ax2.set_ylabel("Aligned witness", fontsize=10)
        # Annotate cells with values
        for i in range(len(ap_num.index)):
            for j in range(len(ap_num.columns)):
                val = ap_num.iloc[i, j]
                if not np.isnan(val):
                    ax2.text(j, i, f"{int(val)}", ha="center", va="center",
                             fontsize=5.5, color="black" if val < 60 else "white")
    else:
        ax2.text(0.5, 0.5, "No all-pairs data found", ha="center", va="center",
                 transform=ax2.transAxes, fontsize=13)
        ax2.set_title("All-pairs alignment rate heatmap")

    fig2.tight_layout()
    fig2.savefig("plot_allpairs_heatmap.png", dpi=150)
    plt.close(fig2)
    print("Saved plot_allpairs_heatmap.png")

    # ──────────────────────────────────────────────────────────────────────────
    # Plot 3: similarity measures grouped bar
    # ──────────────────────────────────────────────────────────────────────────
    SIM_CONFIGS = ["baseline", "dice", "levenshtein", "combined"]

    fig3, ax3 = plt.subplots(figsize=(8, 5))
    if not df_comp.empty:
        first_run = df_comp.drop_duplicates("config", keep="first")
        sim_df = first_run[first_run["config"].isin(SIM_CONFIGS)].copy()
        sim_df = sim_df.set_index("config").reindex(
            [c for c in SIM_CONFIGS if c in sim_df.index]
        )
        cats = sim_df.index.tolist()
        display_names = {"baseline": "Jaccard\n(baseline)", "dice": "Dice",
                         "levenshtein": "Levenshtein", "combined": "Combined\n(Jac+Lev)"}
        cats_labeled = [display_names.get(c, c) for c in cats]
        rates = sim_df["rate"].fillna(0).tolist()
        scores = [v * 100 for v in sim_df["mean_sc"].fillna(0).tolist()]
        _bar_chart(ax3, cats_labeled, rates, scores,
                   "Alignment rate (%)", "Mean score (×100)",
                   "Similarity measures: alignment rate vs mean score",
                   "Value")
    else:
        ax3.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("Similarity measures")

    fig3.tight_layout()
    fig3.savefig("plot_similarity_measures.png", dpi=150)
    plt.close(fig3)
    print("Saved plot_similarity_measures.png")

    # ──────────────────────────────────────────────────────────────────────────
    # Plot 4: section size line chart
    # ──────────────────────────────────────────────────────────────────────────
    SECTION_CONFIGS = [
        ("baseline",  1,  "line=1 (baseline)"),
        ("sections5", 5,  "sections5 (window=5)"),
        ("sections10",10, "sections10 (window=10)"),
    ]

    fig4, ax4 = plt.subplots(figsize=(7, 5))
    if not df_comp.empty:
        first_run = df_comp.drop_duplicates("config", keep="first")
        sec_data = []
        for cname, wsz, label in SECTION_CONFIGS:
            row = first_run[first_run["config"] == cname]
            if not row.empty:
                sec_data.append({
                    "window": wsz,
                    "label": label,
                    "rate":  row.iloc[0]["rate"],
                    "mean_sc": row.iloc[0]["mean_sc"] * 100,
                })
        if sec_data:
            sec_df = pd.DataFrame(sec_data)
            ax4.plot(sec_df["window"], sec_df["rate"], marker="o", color=PALETTE[0],
                     linewidth=2, markersize=8, label="Alignment rate (%)")
            ax4b = ax4.twinx()
            ax4b.plot(sec_df["window"], sec_df["mean_sc"], marker="s", color=PALETTE[1],
                      linewidth=2, markersize=8, label="Mean score (×100)", linestyle="--")
            ax4.set_xlabel("Window size (lines per section)", fontsize=10)
            ax4.set_ylabel("Alignment rate (%)", color=PALETTE[0], fontsize=10)
            ax4b.set_ylabel("Mean score (×100)", color=PALETTE[1], fontsize=10)
            ax4.set_xticks(sec_df["window"].tolist())
            ax4.set_xticklabels([str(int(w)) for w in sec_df["window"].tolist()])
            ax4.set_title("Effect of section window size on alignment", fontsize=11, fontweight="bold")
            lines1, labels1 = ax4.get_legend_handles_labels()
            lines2, labels2 = ax4b.get_legend_handles_labels()
            ax4.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="best")
            ax4.grid(linestyle="--", alpha=0.4)
            ax4.spines["top"].set_visible(False)
        else:
            ax4.text(0.5, 0.5, "No section-size data", ha="center", va="center",
                     transform=ax4.transAxes)
    else:
        ax4.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax4.transAxes)
    ax4.set_title("Effect of section window size on alignment", fontsize=11, fontweight="bold")

    fig4.tight_layout()
    fig4.savefig("plot_section_size.png", dpi=150)
    plt.close(fig4)
    print("Saved plot_section_size.png")

    # ──────────────────────────────────────────────────────────────────────────
    # Summary table
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 90)
    print("SUMMARY TABLE  (first-run values per config)")
    print("=" * 90)

    ALL_CONFIGS_ORDER = [
        "baseline", "dice", "levenshtein", "combined",
        "sections5", "sections10", "positional", "banded", "nw",
    ]

    strategy_map = {
        "baseline": "LIS", "dice": "LIS", "levenshtein": "LIS", "combined": "LIS",
        "sections5": "LIS", "sections10": "LIS", "positional": "LIS", "banded": "LIS",
        "nw": "Needleman-Wunsch",
    }
    notes_map = {
        "baseline":    "Jaccard word-set; production default",
        "dice":        "Dice coefficient; weights shared words more",
        "levenshtein": "Word-level edit distance; respects word order",
        "combined":    "50% Jaccard + 50% Levenshtein",
        "sections5":   "5-line sections merged before comparison",
        "sections10":  "10-line sections merged before comparison",
        "positional":  "Soft positional prior (pos_weight=0.3)",
        "banded":      "Hard band (±15% of anchor length)",
        "nw":          "Global Needleman-Wunsch alignment",
    }

    hdr = f"{'Config':<14} {'Align Rate':>11} {'Mean Score':>11} {'High Conf*':>11} {'Strategy':<22} Notes"
    print(hdr)
    print("-" * len(hdr))

    if not df_comp.empty:
        first_run = df_comp.drop_duplicates("config", keep="first")
        for cname in ALL_CONFIGS_ORDER:
            row = first_run[first_run["config"] == cname]
            if row.empty:
                print(f"  {cname:<12}  (no data)")
                continue
            r = row.iloc[0]
            # high confidence: not directly in table; approximate from mean_sc
            # (we don't have exact high-conf count from this parse)
            rate_s  = f"{r['rate']:.1f}%" if not np.isnan(r["rate"]) else "n/a"
            mean_s  = f"{r['mean_sc']:.3f}" if not np.isnan(r["mean_sc"]) else "n/a"
            strat   = strategy_map.get(cname, "LIS")
            note    = notes_map.get(cname, "")
            print(f"  {cname:<12}  {rate_s:>10}  {mean_s:>10}  {'n/a':>10}  {strat:<22} {note}")
    else:
        print("  (no data parsed)")

    print("\n* High-confidence count not available from table output (would need raw scores).")
    print("  See sample matches in results_all.txt for qualitative assessment.\n")

    # ──────────────────────────────────────────────────────────────────────────
    # Best-anchor analysis from all-pairs
    # ──────────────────────────────────────────────────────────────────────────
    if ap_df is not None and not ap_df.empty:
        ap_num = ap_df.apply(pd.to_numeric, errors="coerce")
        col_means = ap_num.mean(skipna=True)
        best_anchor = col_means.idxmax()
        print(f"Best anchor (highest mean column in all-pairs matrix): {best_anchor}")
        print(f"  Mean alignment rate when used as anchor: {col_means[best_anchor]:.1f}%")
        print(f"\nTop 5 anchors by mean alignment rate:")
        for wid, val in col_means.nlargest(5).items():
            print(f"  {wid}: {val:.1f}%")
    else:
        print("(all-pairs data not available for anchor analysis)")

    print("\nDone. Plots saved to current directory.")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        main()
