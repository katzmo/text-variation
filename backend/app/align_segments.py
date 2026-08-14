"""
align_segments.py — segment alignment for kat-text-tool

Algorithm:
1. Strip TEI noise from each <l> element → clean plain text
2. Build an inverted index of the anchor witness (word → list of positions)
3. For each witness line, find top-K candidate anchor positions via the index
4. Score each candidate with Dice (Sorensen-Dice) similarity
5. Run O(n log n) LIS (Longest Increasing Subsequence) on the scored pairs
   to enforce a monotonic (no-crossing) alignment
6. Return alignment table: witness_local_n → anchor_local_n | None, + score

Key insight about this corpus:
- The 'n' attribute in these TEI files is WITNESS-LOCAL (resets at 1 for each MS)
- Every witness needs pure content-based alignment against the anchor
- LIS enforces monotonicity (order of lines must be preserved)
- Dice on word sets handles Old French spelling variation
"""

import re
import copy
import time
from pathlib import Path
from typing import Optional
from bisect import bisect_left
from lxml import etree

from .lab_similarity import Bundle, sim_dice


# ── Text cleaning ──────────────────────────────────────────────────────────────

# Local tag names (namespace-agnostic) whose text is editorial/structural noise.
# Includes Faust-specific tags (fw page numbers, handShift, anchor, g glyphs) so
# the diplomatic transcripts clean up the same way the align-lab parser does.
DROP_TAGS = {'note', 'erasure', 'crease', 'posthole', 'del',
             'fw', 'handShift', 'anchor', 'g'}


def clean_line_text(el) -> str:
    """Extract plain text from a line element (<l>/<line>), stripping editorial noise."""
    el = copy.deepcopy(el)
    for node in list(el.iter()):
        if node is el:
            continue
        if _strip_ns(node.tag) in DROP_TAGS:
            parent = node.getparent()
            if parent is not None:
                tail = node.tail or ''
                prev = node.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or '') + tail
                else:
                    parent.text = (parent.text or '') + tail
                parent.remove(node)

    def _get_text(node) -> str:
        parts = [node.text or '']
        for child in node:
            parts.append(_get_text(child))
            parts.append(child.tail or '')
        return ''.join(parts)

    text = _get_text(el)
    text = re.sub(r'[^\w\s]', '', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


# ── Witness loading ────────────────────────────────────────────────────────────

# Tags whose text content is editorial noise, stripped when reading lb-style lines
_INLINE_DROP = {'note', 'del'}


def _clean_text_string(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = re.sub(r'[^\w\s]', '', text.lower())
    return re.sub(r'\s+', ' ', text).strip()


def _strip_ns(tag) -> str:
    """Return the local tag name without namespace."""
    if isinstance(tag, str) and '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def _collect_lb_pairs(tree) -> list:
    """Walk a milestone-style TEI where <lb n="N"/> marks line beginnings and the
    line text is the tail/following content up to the next <lb/>. Returns the
    kept segments as (lb_element, clean_text) pairs — only <lb/>s that carry a
    numeric `n` and non-empty text, matching load_witness_lb's filtering exactly.
    Both the loader and the XML annotator build on this so they never diverge."""
    pairs = []
    # Find all lb elements in document order, namespace-agnostic
    lbs = [el for el in tree.iter() if _strip_ns(el.tag) == 'lb']
    for i, lb in enumerate(lbs):
        n = lb.get('n')
        if not n:
            continue
        # Collect text: the lb's tail, plus the text of following siblings/descendants
        # until the next lb. We walk the document from this lb to the next lb.
        parts = [lb.tail or '']
        # Walk subsequent nodes in document order until we hit the next lb
        nxt = lbs[i + 1] if i + 1 < len(lbs) else None
        # Use iter over the whole tree is expensive; instead walk siblings/parents
        for el in lb.itersiblings():
            if el is nxt:
                break
            if _strip_ns(el.tag) in _INLINE_DROP:
                parts.append(el.tail or '')
                continue
            # include element text and tail and descendants' text
            parts.append(_element_text_until(el, nxt))
            if nxt is not None and _contains(el, nxt):
                break
        text = _clean_text_string(''.join(parts))
        if not text:
            continue
        try:
            int(n)
        except ValueError:
            continue
        pairs.append((lb, text))
    return pairs


def load_witness_lb(tree) -> list:
    """
    Load lines from a milestone-style TEI where <lb n="N"/> marks line beginnings.
    Returns list of (local_n: int, clean_text: str).
    """
    return [(int(lb.get('n')), text) for lb, text in _collect_lb_pairs(tree)]


def _element_text_until(el, stop) -> str:
    """Concatenate text of el and descendants and tails, stopping at `stop`."""
    parts = []
    for node in el.iter():
        if node is stop:
            break
        if _strip_ns(node.tag) in _INLINE_DROP:
            continue
        parts.append(node.text or '')
    parts.append(el.tail or '')
    return ''.join(parts)


def _contains(el, target) -> bool:
    """True if target is a descendant of el."""
    if target is None:
        return False
    for node in el.iter():
        if node is target:
            return True
    return False


# Editorial tags dropped from a tag-unit's text. Mirrors align-lab parsers.py
# DROP_TAGS so segmenting by --tags here matches Katharina's CLI exactly.
_TAG_DROP = {'note', 'del', 'erasure', 'crease', 'posthole'}


def _tag_element_text(el) -> str:
    """Concatenate the descendant text of a tag-unit element, skipping editorial
    noise. Namespace-agnostic port of align-lab parsers._element_text (which
    joins each node's .text, not its tail)."""
    parts = []
    for node in el.iter():
        if _strip_ns(node.tag) in _TAG_DROP:
            continue
        parts.append(node.text or '')
    return ''.join(parts)


def _xpath_tags(tree, tags: list, within_body: bool):
    """Elements whose local name is one of `tags`, in document order.
    Mirrors align-lab parsers.load_segments: namespaced via the default xmlns,
    optionally scoped to <body>."""
    root = tree.getroot()
    xmlns = root.nsmap.get(None) if hasattr(root, 'nsmap') else None
    if xmlns:
        step = "ns:body//ns:" if within_body else "ns:"
        expr = "|".join(f".//{step}{t}" for t in tags)
        return tree.xpath(expr, namespaces={"ns": xmlns})
    step = "body//" if within_body else ""
    expr = "|".join(f".//{step}{t}" for t in tags)
    return tree.xpath(expr)


def _has_body(tree) -> bool:
    """True if the document contains a <body> element (namespace-agnostic)."""
    return any(_strip_ns(e.tag) == 'body' for e in tree.iter())


_FAUST_NS = "http://www.faustedition.net/ns"


def _line_number(el, fallback: int) -> int:
    """Line number from f:nx / nx / n (trailing digits), else a sequential fallback.
    Faust verse lines carry the number in f:nx="t3_42"; <l n="42"> uses a plain n."""
    raw = el.get(f"{{{_FAUST_NS}}}nx") or el.get('nx') or el.get('n')
    if raw:
        m = re.search(r'(\d+)$', raw)
        if m:
            return int(m.group(1))
    return fallback


def collect_segments(tree, tags: Optional[list] = None):
    """
    Return (dialect, [(element, clean_text), ...]) — the segment elements of a
    witness, in document order, using the exact same cascade and filtering as the
    aligner. Both load_witness (numbering / alignment) and annotate_witness_xml
    (id injection into served XML) build on this single source of truth, so the
    intrinsic seg_id of a segment is the same string in both places.

    Dialect is one of "tags" / "l" / "line" / "lb". Empty-text entries may be
    present for the "tags"/"l"/"line" dialects; callers number only the non-empty
    ones. The "lb" dialect is pre-filtered (numeric n + non-empty text).

    If `tags` is given (e.g. ['p', 'lg']), segment by those TEI tags instead of
    lines — the "tags to use as segments" option mirroring align-lab's --tags CLI.
    Otherwise cascade over three TEI dialects (first that yields text wins):
      <l>    container / verse lines (incl. Faust <l f:nx="t3_N">)
      <line> diplomatic page lines (Faust page transcripts)
      <lb/>  milestone markers (Armenian Matenadaran corpus)
    """
    if tags:
        elements = _xpath_tags(tree, tags, within_body=True)
        if not elements and not _has_body(tree):
            # Only when the file has no <body> at all: retry over the whole tree so
            # a tag the user typed still segments. (When a <body> exists we stay
            # scoped to it, like align-lab's CLI, to avoid grabbing teiHeader text.)
            elements = _xpath_tags(tree, tags, within_body=False)
        pairs = [(el, _clean_text_string(_tag_element_text(el))) for el in elements]
        if any(t for _el, t in pairs):
            return "tags", pairs
        if 'lb' in tags:
            return "lb", _collect_lb_pairs(tree)
        return "tags", pairs

    l_pairs = [(el, clean_line_text(el)) for el in tree.iter() if _strip_ns(el.tag) == 'l']
    if any(t for _el, t in l_pairs):
        return "l", l_pairs
    line_pairs = [(el, clean_line_text(el)) for el in tree.iter() if _strip_ns(el.tag) == 'line']
    if any(t for _el, t in line_pairs):
        return "line", line_pairs
    return "lb", _collect_lb_pairs(tree)


def _lines_from_segments(dialect: str, pairs: list) -> list:
    """Turn collect_segments output into the (local_n, clean_text) list, skipping
    empty segments. The 0-based position within this filtered list is a segment's
    intrinsic id position; local_n is only a display label (dialect-specific)."""
    lines = []
    for el, text in pairs:
        if not text:
            continue
        if dialect == "l":
            n = _line_number(el, len(lines) + 1)
        elif dialect == "lb":
            n = int(el.get('n'))
        else:  # "line" / "tags": sequential
            n = len(lines) + 1
        lines.append((n, text))
    return lines


def load_witness_tags(tree, tags: list) -> list:
    """Segment a witness by TEI tags (e.g. ['p', 'lg']). Kept for compatibility;
    delegates to collect_segments. Returns list of (seq_index, clean_text)."""
    return _lines_from_segments(*collect_segments(tree, tags))


def load_witness(path: Path, tags: Optional[list] = None) -> list:
    """Return list of (local_n: int, clean_text: str) for a witness file."""
    try:
        tree = etree.parse(str(path))
        return _lines_from_segments(*collect_segments(tree, tags))
    except etree.XMLSyntaxError:
        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
        return [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip()]


def _seg_id(witness_id: str, unit: str, pos: int) -> str:
    """Intrinsic segment id: "{wid}:{unit}:{pos}" when a segmentation unit is set,
    else "{wid}:{pos}". `pos` is the segment's 0-based position in its own text.
    Mirrors the scheme in main.align_matrix so DOM data-ids match the score keys."""
    return f"{witness_id}:{unit}:{pos}" if unit else f"{witness_id}:{pos}"


def annotate_witness_xml(path: Path, witness_id: str,
                         tags: Optional[list] = None, unit: str = "",
                         groups: Optional[dict] = None) -> str:
    """Parse a witness TEI file and inject a `data-id` attribute onto every
    segment element, carrying that segment's intrinsic seg_id. Returns the
    serialized XML as a string. `tags`/`unit` should match the alignment run so
    the injected ids line up with the stored pairwise scores.

    If `groups` (a seg_id -> group_id map, #9) is given, each segment that belongs
    to a shared "reading" group also gets a `data-group` attribute, so the frontend
    can highlight the whole reading across all texts when one member is clicked.

    `data-id`/`data-group` (plain, unnamespaced attributes) are used rather than
    xml:id because seg_ids contain ':' and are not valid XML NCNames."""
    tree = etree.parse(str(path))
    dialect, pairs = collect_segments(tree, tags)
    pos = 0
    for el, text in pairs:
        if not text:
            continue
        sid = _seg_id(witness_id, unit, pos)
        el.set("data-id", sid)
        if groups:
            gid = groups.get(sid)
            if gid:
                el.set("data-group", gid)
        pos += 1
    return etree.tostring(tree, encoding="unicode")


# ── Similarity ────────────────────────────────────────────────────────────────

def jaccard(a: str, b: str) -> float:
    sa = set(a.split())
    sb = set(b.split())
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Index ─────────────────────────────────────────────────────────────────────

def build_index(lines: list, min_word_len: int = 3) -> dict:
    """Inverted index: word → [positions in anchor]."""
    idx: dict = {}
    for pos, (n, text) in enumerate(lines):
        for w in set(text.split()):
            if len(w) > min_word_len:
                if w not in idx:
                    idx[w] = []
                idx[w].append(pos)
    return idx


# ── LIS (O(n log n) patience sorting) ─────────────────────────────────────────

def lis_alignment(raw_matches: list) -> list:
    """Extract longest monotone subsequence from (wit_pos, anc_pos, score) triples."""
    if not raw_matches:
        return []
    n = len(raw_matches)
    tails: list = []
    tail_indices: list = []
    parent: list = [-1] * n

    for i, (wi, ap, sc) in enumerate(raw_matches):
        j = bisect_left(tails, ap)
        if j == len(tails):
            tails.append(ap)
            tail_indices.append(i)
        else:
            tails[j] = ap
            tail_indices[j] = i
        parent[i] = tail_indices[j - 1] if j > 0 else -1

    path: list = []
    cur = tail_indices[-1]
    while cur != -1:
        path.append(raw_matches[cur])
        cur = parent[cur]
    path.reverse()

    kept: list = []
    last_anc = -1
    for item in path:
        if item[1] > last_anc:
            kept.append(item)
            last_anc = item[1]
    return kept


# ── Main alignment function ────────────────────────────────────────────────────

def align_witness(
    witness_lines: list,
    anchor_lines: list,
    anchor_idx: dict,
    threshold: float = 0.1,
    top_k: int = 15,
    min_word_len: int = 3,
    anchor_sets: list = None,
) -> list:
    """
    Align a witness against the anchor.
    Returns list of dicts with keys:
      witness_n, anchor_n (None if unaligned), anchor_pos, score, text, anchor_text

    anchor_sets: optional precomputed list of Bundles for each anchor line.
    Passing it avoids rebuilding the anchor bundles on every comparison, which is
    a large speed-up when aligning many witnesses against the same anchor.
    """
    # Precompute anchor bundles once (caller can also pass them in)
    if anchor_sets is None:
        anchor_sets = [Bundle(t) for (_n, t) in anchor_lines]

    raw_matches: list = []
    for wi, (wn, wt) in enumerate(witness_lines):
        w_words = wt.split()
        cands: dict = {}
        for w in w_words:
            if len(w) > min_word_len:
                posting = anchor_idx.get(w)
                if posting:
                    for pos in posting:
                        cands[pos] = cands.get(pos, 0) + 1
        if not cands:
            continue
        # Precompute the witness line's bundle once, reuse for all candidates
        wb = Bundle(wt)
        top = sorted(cands.items(), key=lambda x: -x[1])[:top_k]
        best_pos, best_score = -1, 0.0
        for pos, _ in top:
            s = sim_dice(wb, anchor_sets[pos])
            if s > best_score:
                best_score = s
                best_pos = pos
        if best_score >= threshold:
            raw_matches.append((wi, best_pos, best_score))

    kept = lis_alignment(raw_matches)
    kept_dict: dict = {wi: (ap, sc) for wi, ap, sc in kept}

    result = []
    for wi, (wn, wt) in enumerate(witness_lines):
        if wi in kept_dict:
            ap, sc = kept_dict[wi]
            an, at = anchor_lines[ap]
            result.append({
                "witness_n":   wn,
                "witness_pos": wi,
                "anchor_n":    an,
                "anchor_pos":  ap,
                "score":       round(sc, 4),
                "text":        wt,
                "anchor_text": at,
            })
        else:
            result.append({
                "witness_n":   wn,
                "witness_pos": wi,
                "anchor_n":    None,
                "anchor_pos":  None,
                "score":       0.0,
                "text":        wt,
                "anchor_text": None,
            })
    return result


# ── All-pairs cross-witness alignment (#2) ─────────────────────────────────────

def _pair_edges(bundles_a: list, bundles_b: list, index_b: dict,
                threshold: float, top_k: int, min_word_len: int) -> list:
    """Greedy one-to-one best matches from witness A's segments to witness B's.
    Returns [(pos_a, pos_b, dice_score), ...].

    Transposition-tolerant: unlike lis_alignment there is NO monotonicity
    requirement. Each A-segment shortlists candidate B-positions via B's inverted
    index, scores them with Dice, and the highest-scoring pairs are assigned
    first, each segment used at most once. Mirrors align-lab's updated
    two_pass_lis greedy assignment, so a segment that is similar but out of order
    still gets related to its twin instead of being dropped."""
    raw = []
    for pa, ba in enumerate(bundles_a):
        cands: dict = {}
        for w in ba.wset:
            if len(w) > min_word_len:
                for pb in index_b.get(w, ()):
                    cands[pb] = cands.get(pb, 0) + 1
        if not cands:
            continue
        top = sorted(cands.items(), key=lambda x: -x[1])[:top_k]
        for pb, _ in top:
            s = sim_dice(ba, bundles_b[pb])
            if s >= threshold:
                raw.append((pa, pb, s))
    raw.sort(key=lambda x: -x[2])
    used_a, used_b = set(), set()
    edges = []
    for pa, pb, s in raw:
        if pa in used_a or pb in used_b:
            continue
        used_a.add(pa)
        used_b.add(pb)
        edges.append((pa, pb, round(s, 4)))
    return edges


def build_relations(witness_segments: dict, threshold: float = 0.1,
                    top_k: int = 15, min_word_len: int = 3) -> list:
    """All-pairs cross-witness alignment (#2).

    witness_segments: {witness_id: [(local_n, clean_text), ...]} in intrinsic
    position order (i.e. load_witness output per witness).

    Returns edges [(wid_a, pos_a, wid_b, pos_b, dice_score), ...] for every
    unordered witness pair (wid_a < wid_b), keeping every segment. There is no
    single anchor: witnesses are related directly to each other, and the greedy
    one-to-one matching per pair tolerates transposition. `threshold` is kept low
    so few real relations are lost — filtering by score is a display concern (#7),
    not something baked into the graph."""
    wids = sorted(witness_segments)
    bundles = {w: [Bundle(t) for (_n, t) in witness_segments[w]] for w in wids}
    indices = {w: build_index(witness_segments[w], min_word_len) for w in wids}

    edges = []
    for i in range(len(wids)):
        for j in range(i + 1, len(wids)):
            wa, wb = wids[i], wids[j]
            for pa, pb, s in _pair_edges(bundles[wa], bundles[wb], indices[wb],
                                         threshold, top_k, min_word_len):
                edges.append((wa, pa, wb, pb, s))
    return edges


def alignment_stats(alignment: list, threshold: float) -> dict:
    total = len(alignment)
    aligned = [a for a in alignment if a["anchor_n"] is not None]
    n_aligned = len(aligned)
    avg_score = sum(a["score"] for a in aligned) / n_aligned if aligned else 0.0
    high_conf = sum(1 for a in aligned if a["score"] >= min(threshold + 0.2, 0.9))
    return {
        "total":       total,
        "aligned":     n_aligned,
        "unaligned":   total - n_aligned,
        "pct_aligned": round(100 * n_aligned / total, 1) if total else 0.0,
        "avg_score":   round(avg_score, 3),
        "high_conf":   high_conf,
        "threshold":   threshold,
    }


def save_augmented_tei(source_path: Path, dest_path: Path, alignment: list, witness_id: str):
    """Write TEI with xml:id added to each line. aligned → line-NNNNN, else line-WID-NNNNN.
    Handles both <l> container style and <lb/> milestone style."""
    n_to_anchor: dict = {a["witness_n"]: a["anchor_n"] for a in alignment}
    tree = etree.parse(str(source_path))
    XML_NS = "http://www.w3.org/XML/1998/namespace"

    def tag_element(el):
        n_str = el.get('n')
        if not n_str:
            return
        try:
            wn = int(n_str)
        except ValueError:
            return
        anchor_n = n_to_anchor.get(wn)
        xml_id = f"line-{anchor_n:05d}" if anchor_n is not None else f"line-{witness_id}-{wn:05d}"
        el.set(f"{{{XML_NS}}}id", xml_id)

    l_elements = tree.findall('.//l')
    if l_elements:
        for l in l_elements:
            tag_element(l)
    else:
        # Milestone style: tag the <lb/> elements
        for el in tree.iter():
            tag = el.tag
            if isinstance(tag, str) and (tag == 'lb' or tag.endswith('}lb')):
                tag_element(el)

    tree.write(str(dest_path), xml_declaration=True, encoding="UTF-8", pretty_print=False)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/mnt/user-data/uploads")
    anchor_id = sys.argv[2] if len(sys.argv) > 2 else "A"
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 0.35

    print(f"Loading witnesses from {data_dir} | anchor={anchor_id} | threshold={threshold}")
    t0 = time.time()
    anchor_path = data_dir / f"{anchor_id}.xml"
    anchor_lines = load_witness(anchor_path)
    anchor_idx = build_index(anchor_lines)
    print(f"Anchor {anchor_id}: {len(anchor_lines)} lines\n")

    for path in sorted(data_dir.glob("*.xml")):
        wid = path.stem
        if wid == anchor_id:
            continue
        t1 = time.time()
        lines = load_witness(path)
        alignment = align_witness(lines, anchor_lines, anchor_idx, threshold=threshold)
        stats = alignment_stats(alignment, threshold)
        bar = '█' * int(stats['pct_aligned'] / 3)
        print(f"  {wid:4s}: {stats['aligned']:5d}/{stats['total']:5d} "
              f"({stats['pct_aligned']:5.1f}%) avg={stats['avg_score']:.3f}  {bar}")

    print(f"\nTotal: {time.time()-t0:.2f}s")
