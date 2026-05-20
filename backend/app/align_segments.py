"""
align_segments.py — segment alignment for kat-text-tool

Algorithm:
1. Strip TEI noise from each <l> element → clean plain text
2. Build an inverted index of the anchor witness (word → list of positions)
3. For each witness line, find top-K candidate anchor positions via the index
4. Score each candidate with Jaccard similarity
5. Run O(n log n) LIS (Longest Increasing Subsequence) on the scored pairs
   to enforce a monotonic (no-crossing) alignment
6. Return alignment table: witness_local_n → anchor_local_n | None, + score

Key insight about this corpus:
- The 'n' attribute in these TEI files is WITNESS-LOCAL (resets at 1 for each MS)
- Every witness needs pure content-based alignment against the anchor
- LIS enforces monotonicity (order of lines must be preserved)
- Jaccard on word sets handles Old French spelling variation
"""

import re
import copy
import time
from pathlib import Path
from typing import Optional
from bisect import bisect_left
from lxml import etree


# ── Text cleaning ──────────────────────────────────────────────────────────────

DROP_TAGS = {'note', 'erasure', 'crease', 'posthole', 'del'}


def clean_line_text(el) -> str:
    """Extract plain text from a <l>, stripping editorial noise."""
    el = copy.deepcopy(el)
    for tag in DROP_TAGS:
        for node in el.iter(tag):
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


def load_witness_lb(tree) -> list:
    """
    Load lines from a milestone-style TEI where <lb n="N"/> marks line beginnings
    and the line text is the tail content following each <lb/> up to the next one.
    Returns list of (local_n: int, clean_text: str).
    """
    lines = []
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
        node = lb
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
        if text:
            try:
                lines.append((int(n), text))
            except ValueError:
                pass
    return lines


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


def load_witness(path: Path) -> list:
    """
    Return list of (local_n: int, clean_text: str).
    Tries <l> container style first; if none found, falls back to <lb/> milestone style.
    """
    tree = etree.parse(str(path))
    lines = []
    for l in tree.findall('.//l'):
        n = l.get('n')
        text = clean_line_text(l)
        if n and text:
            try:
                lines.append((int(n), text))
            except ValueError:
                pass
    if not lines:
        # Milestone style (lb markers with floating tail text)
        lines = load_witness_lb(tree)
    return lines


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
    threshold: float = 0.35,
    top_k: int = 15,
    min_word_len: int = 3,
    anchor_sets: list = None,
) -> list:
    """
    Align a witness against the anchor.
    Returns list of dicts with keys:
      witness_n, anchor_n (None if unaligned), anchor_pos, score, text, anchor_text

    anchor_sets: optional precomputed list of word-sets for each anchor line.
    Passing it avoids rebuilding the anchor sets on every comparison, which is a
    large speed-up when aligning many witnesses against the same anchor.
    """
    # Precompute anchor word sets once (caller can also pass them in)
    if anchor_sets is None:
        anchor_sets = [set(t.split()) for (_n, t) in anchor_lines]

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
        # Precompute the witness line's word set once, reuse for all candidates
        wset = set(w_words)
        top = sorted(cands.items(), key=lambda x: -x[1])[:top_k]
        best_pos, best_score = -1, 0.0
        for pos, _ in top:
            aset = anchor_sets[pos]
            if not wset and not aset:
                s = 1.0
            elif not wset or not aset:
                s = 0.0
            else:
                inter = len(wset & aset)
                s = inter / (len(wset) + len(aset) - inter)
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
                "anchor_n":    an,
                "anchor_pos":  ap,
                "score":       round(sc, 4),
                "text":        wt,
                "anchor_text": at,
            })
        else:
            result.append({
                "witness_n":   wn,
                "anchor_n":    None,
                "anchor_pos":  None,
                "score":       0.0,
                "text":        wt,
                "anchor_text": None,
            })
    return result


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
