"""
parsers.py — read TEI witnesses into comparable units.

Two things happen here:
  1. load_segments(path, tags)  -> xml_id, [clean_text, ...] one entry per segment
       Handles BOTH conventional <l>...</l> containers AND the milestone
       <lb n="1"/> style where text floats as tail content after the marker.
  2. group_units(lines, window) -> [unit, ...]      where a unit is a dict
       {idx, n0, n1, text}. window=1 gives 1 segment; window=5/10/... merges
       consecutive segments into larger sections (Katharina's point #1).
"""
import re
from lxml import etree

# Editorial tags whose text is noise for comparison (notes, deletions, etc.)
DROP_TAGS = {"note", "del", "erasure", "crease", "posthole"}


def _local(tag):
    """Tag name without its XML namespace."""
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _clean(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    text = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _element_text(el):
    """All text inside an element, skipping DROP_TAGS, no namespace fuss."""
    parts = []
    for node in el.iter():
        if _local(node.tag) in DROP_TAGS:
            continue
        parts.append(node.text or "")
    return "".join(parts)


def _element_text_until(el, stop):
    parts = []
    for node in el.iter():
        if node is stop:
            break
        if _local(node.tag) in DROP_TAGS:
            continue
        parts.append(node.text or "")
    parts.append(el.tail or "")
    return "".join(parts)


def _contains(el, target):
    if target is None:
        return False
    for node in el.iter():
        if node is target:
            return True
    return False


def _load_milestone(tree):
    """Milestone <lb/> style: text is the tail after each marker."""
    lines = []
    lbs = [el for el in tree.iter() if _local(el.tag) == "lb"]
    for i, lb in enumerate(lbs):
        n = lb.get("n")
        if not n:
            continue
        nxt = lbs[i + 1] if i + 1 < len(lbs) else None
        parts = [lb.tail or ""]
        for el in lb.itersiblings():
            if el is nxt:
                break
            if _local(el.tag) in DROP_TAGS:
                parts.append(el.tail or "")
                continue
            parts.append(_element_text_until(el, nxt))
            if nxt is not None and _contains(el, nxt):
                break
        text = _clean("".join(parts))
        if text:
            try:
                lines.append((int(n), text))
            except ValueError:
                pass
    return lines


def load_segments(path, tags):
    """Return (xml_id, [clean_text, ...]) for one witness file."""
    tree = etree.parse(str(path))
    # Is there an ID?
    xml_id = tree.getroot().get("{http://www.w3.org/XML/1998/namespace}id")
    # Is there a namespace?
    if xmlns := tree.getroot().nsmap.get(None):
        ns = "ns" # custom prefix for the default namespace
        elements = tree.xpath("|".join(f".//{ns}:body//{ns}:{tag}" for tag in tags), namespaces={ns: xmlns})
    else:
        elements = tree.xpath("|".join(f".//body//{tag}" for tag in tags))
    # Find segments
    segments = []
    for el in elements:
        text = _clean(_element_text(el))
        if text:
            segments.append(text)
    if not segments and "lb" in tags:
        segments = _load_milestone(tree)
    return xml_id, segments


def group_units(lines, window=1):
    """
    Group consecutive lines into units of `window` lines each.
    window=1 -> line-level (current production behaviour).
    window=5 -> each unit is 5 lines joined (a 'larger section').
    Returns a list of dicts: {idx, n0, n1, text}.
    """
    units = []
    if window <= 1:
        for i, text in enumerate(lines):
            units.append({"idx": i, "n0": i, "n1": i, "text": text})
        return units
    for i in range(0, len(lines), window):
        chunk = lines[i : i + window]
        text = " ".join(t for t in chunk)
        units.append({
            "idx": len(units),
            "n0": chunk[0][0],
            "n1": chunk[-1][0],
            "text": text,
        })
    return units
