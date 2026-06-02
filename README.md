# align-lab — alignment experimentation harness

A standalone sandbox for trying out alignment ideas **without touching the
production tool**. Nothing here imports the real `kat-text-tool` code, so you
can change anything freely. Once an approach wins, we port that single
configuration back into `backend/app/align_segments.py`.

## Run it

```bash
cd align-lab
python lab.py                 # compare all configs on the sample pair
python lab.py --list          # list the named configs
python lab.py --config dice   # run one config + show sample matches
python lab.py --all-pairs     # every text as anchor (rate matrix)
python lab.py --data my_dir   # use your own folder of .xml TEI files
```

Requires only Python 3 and `lxml` (`pip install lxml`). Put more TEI files in
`./data` (or pass `--data`) to test on a bigger corpus.

## How the knobs map to Katharina's notes

| Note | Knob in a config | Values |
|------|------------------|--------|
| #1 larger sections (p, lg) | `window` | `1` = lines, `5`/`10` = merged sections |
| #2 every text as anchor | `--all-pairs` | runs an N×N rate matrix |
| #3 experiment with algorithm | `strategy` | `lis` (current) or `nw` (global Needleman-Wunsch) |
| #4 prefer similar position | `band_frac` / `pos_weight` | e.g. `0.15` hard band, `0.3` soft prior |
| #5 order of words matters | `similarity` | `jaccard`, `dice`, `bigram`, `levenshtein`, `combined` |

A config is just a dict in `CONFIGS` in `lab.py`. Add your own, e.g.:

```python
"my_idea": dict(window=5, similarity="combined", strategy="lis", band_frac=0.2),
```

## What the metrics mean

- **rate** — % of witness units that got aligned.
- **aligned** — count of aligned units.
- **mean_sc** — average similarity of the aligned matches (quality, not just quantity).
- **mono** — monotonicity: are matches in reading order? `lis`/`nw` guarantee 1.00; a soft positional prior might not.
- **anc_cov** — % of anchor units that received at least one match (spread).
- **agree** — where two methods both align a line, do they pick the same target? High agreement on high scores is a good sign the matches are real.

**Important:** a higher rate is *not* automatically better — it can mean more
false matches. Always read `mean_sc` alongside `rate`, and eyeball the sample
matches the script prints.

## Files

- `parsers.py` — read TEI (both `<l>` and `<lb/>` milestone styles); group lines into sections.
- `similarity.py` — Jaccard, Dice, bigram-Jaccard, word-Levenshtein, combined.
- `strategies.py` — `two_pass_lis` (current approach + band/positional options) and `needleman_wunsch` (banded global).
- `evaluate.py` — metrics, cross-config agreement, sample matches.
- `lab.py` — runner, named configs, CLI.

## Suggested workflow

1. **Eyeball, don't just chase rate.** Run `python lab.py` and read the table
   *and* the sample matches together. A config that aligns more lines but with
   lower `mean_sc` may just be inventing matches.
2. **Make a tiny gold standard.** The rigorous way to compare is to hand-align
   ~50 lines of one witness pair (you or Katharina), save it as a small CSV of
   `witness_n, anchor_n`, and measure precision/recall against it. This turns
   "looks better" into a real number. If you want, I can add a `--gold` mode
   that reads such a file and reports precision/recall.
3. **Test the winner across pairs.** Use `--all-pairs` to check the chosen
   config holds up no matter which text is the anchor (Katharina #2).
4. **Then port one config** back into production. The production code already
   has the `lis` path; the new pieces (a similarity swap, a band, sections)
   are small, isolated changes.

## Early observations on the sample pair (BZ430 vs BZ449)

These are first impressions from two witnesses only — not conclusions.

- **Dice** aligned about twice as many lines as Jaccard at a *higher* mean
  score, and agreed 100% with the baseline where they overlapped. Promising.
- **Word-Levenshtein** and **combined** behaved like Jaccard here but a little
  higher quality, at some speed cost. Worth keeping for order-sensitive cases.
- **Larger sections** (window 5/10) *reduced* alignment on this pair, because
  the two witnesses diverge enough that whole 5–10 line blocks rarely match as
  a unit. Sections may help more on closely related witnesses; test per pair.
- **Hard band** and **NW** were too restrictive here — expected, since these
  two witnesses are offset and fragmentary, so position is a weak prior. They
  may shine on witnesses that really are in near-lockstep.

Bottom line so far: try **Dice** (and **combined** for quality) before anything
else, and treat sections/banding as per-pair options rather than global wins.
