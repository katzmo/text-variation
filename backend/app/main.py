"""
kat-text-tool — FastAPI backend
Endpoints:
  GET  /api/witnesses           → list witnesses in data dir
  GET  /api/witnesses/{id}/xml  → raw TEI XML
  GET  /api/segments            → all segment texts
  GET  /api/matrix              → pairwise distance matrix
  POST /api/collate             → collate a segment via CollateX
  GET  /api/stemma              → UPGMA dendrogram
  POST /api/upload              → upload TEI/txt files + optional CSV metadata
  POST /api/upload/confirm      → confirm metadata and finalise witness set
  GET  /api/align/witnesses     → witnesses available for alignment + line counts
  POST /api/align/run           → run line alignment against an anchor
  GET  /api/align/inspect/{id}  → paginated alignment results for one witness
  GET  /api/align/witnesses/{id}/scores → all pairwise scores for one witness (batch)
  POST /api/align/save          → write augmented TEI files
"""

import os, json, math, csv, io, shutil, hashlib, re
from pathlib import Path
from typing import Optional
# lxml (not stdlib ElementTree) so upload parsing matches the alignment engine and
# the alignment lab: it tolerates TEI quirks stdlib rejects, e.g. a non-canonical
# encoding label like <?xml ... encoding='UTF8'?> which breaks expat on non-ASCII text.
from lxml import etree as ET

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
import collatex

# ── paths ──────────────────────────────────────────────────────────
DATA_DIR     = Path(os.getenv("DATA_DIR",     "/app/data/witnesses"))
UPLOAD_DIR   = Path(os.getenv("UPLOAD_DIR",   "/app/data/uploads"))
TEI_NS       = "http://www.tei-c.org/ns/1.0"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

from . import scores_db as _scores_db
_scores_db.init_db(DATA_DIR)

app = FastAPI(title="kat-text-tool API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── TEI parsing ────────────────────────────────────────────────────

def parse_witness(path: Path) -> dict:
    tree = ET.parse(str(path))
    root = tree.getroot()
    ns = {"tei": TEI_NS}
    segments = {}
    for tag in ("p", "lg", "l", "ab"):
        for el in root.findall(f".//tei:{tag}[@{{http://www.w3.org/XML/1998/namespace}}id]", ns):
            seg_id = el.get("{http://www.w3.org/XML/1998/namespace}id")
            parts = []
            if el.text: parts.append(el.text.strip())
            for child in el:
                if child.text: parts.append(child.text.strip())
                if child.tail: parts.append(child.tail.strip())
            segments[seg_id] = " ".join(p for p in parts if p)
    title_el  = root.find(".//tei:title",  ns)
    date_el   = root.find(".//tei:date",   ns)
    origin_el = root.find(".//tei:pubPlace", ns)
    return {
        "id":       path.stem,
        "title":    title_el.text  if title_el  is not None else path.stem,
        "year":     (lambda s: int(m.group()) if (m := re.search(r'\d{4}', s)) else None)(
                        date_el.get("when", date_el.text or "")
                    ) if date_el is not None else None,
        "origin":   origin_el.text if origin_el is not None else None,
        "segments": segments,
    }

def parse_plain(path: Path) -> dict:
    """Parse plain text: each non-empty line is a segment."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    segments = {f"row-{str(i+1)}": l for i, l in enumerate(lines)}
    return {"id": path.stem, "title": path.stem, "year": None, "origin": None, "segments": segments}

# ── helpers ────────────────────────────────────────────────────────

def list_witness_files():
    return sorted(DATA_DIR.glob("*.xml")) + sorted(DATA_DIR.glob("*.txt"))

def jaccard(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb: return 1.0
    return len(sa & sb) / len(sa | sb)

def levenshtein_norm(a: str, b: str) -> float:
    wa, wb = a.lower().split(), b.lower().split()
    m, n = len(wa), len(wb)
    if m == 0 and n == 0: return 1.0
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            cost = 0 if wa[i-1] == wb[j-1] else 1
            dp[j] = min(dp[j-1]+1, prev[j]+1, prev[j-1]+cost)
    return 1 - dp[n] / max(m, n)

# ── routes ─────────────────────────────────────────────────────────

@app.get("/api/witnesses")
def get_witnesses():
    result = []
    # Load metadata sidecar if exists
    meta_path = DATA_DIR / "_metadata.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    for f in list_witness_files():
        if f.stem.startswith("_"): continue
        w = parse_witness(f) if f.suffix == ".xml" else {"id": f.stem, "title": f.stem, "year": None, "origin": None, "segments": {}}
        m = meta.get(f.stem, {})
        result.append({
            "id":          w["id"],
            "name":        m.get("name",        w["title"]),
            "year":        m.get("year",        w["year"]),
            "affiliation": m.get("affiliation", ""),
            "source":      m.get("source",      ""),
            "country":     m.get("country",     w["origin"] or ""),
            "lat":         m.get("lat",         0),
            "lng":         m.get("lng",         0),
            "segments":    list(w["segments"].keys()),
        })
    return result

@app.get("/api/witnesses/{witness_id}/xml")
def get_witness_xml(witness_id: str):
    """Serve a witness's TEI with a `data-id` on every segment element, so the
    frontend can render the full text in original order and address each segment
    (to show its aligned partners and scores). The ids use the same intrinsic
    scheme and segmentation (tags/unit) as the most recent alignment run, so they
    match the score keys. Falls back to the raw file if annotation fails; .txt
    files (non-XML) are served as-is."""
    xml_path = DATA_DIR / f"{witness_id}.xml"
    if xml_path.exists():
        tags = _ALIGN_ANCHOR.get("tags") or None
        unit = _ALIGN_ANCHOR.get("unit") or ""
        # Also stamp a shared `data-group` (#9) at the default grouping threshold,
        # so clicking a fragment can highlight its reading across all texts with a
        # pure CSS selector. The frontend can re-sync groups at another threshold
        # via /api/align/groups without re-fetching the text.
        groups = _compute_groups(GROUP_THRESHOLD)[1] if _RELATIONS else None
        try:
            content = _align.annotate_witness_xml(
                xml_path, witness_id, tags=tags, unit=unit, groups=groups)
        except Exception:
            content = xml_path.read_text()
        return Response(content=content, media_type="application/xml")
    txt_path = DATA_DIR / f"{witness_id}.txt"
    if txt_path.exists():
        return Response(content=txt_path.read_text(), media_type="text/plain")
    raise HTTPException(404, f"Witness {witness_id} not found")

@app.get("/api/segments")
def get_segments():
    result = {}
    for f in list_witness_files():
        if f.stem.startswith("_"): continue
        w = parse_witness(f) if f.suffix == ".xml" else {"id": f.stem, "segments": {}}
        result[w["id"]] = w["segments"]
    return result

@app.get("/api/matrix")
def get_matrix():
    witnesses = []
    for f in list_witness_files():
        if f.stem.startswith("_"): continue
        w = parse_witness(f) if f.suffix == ".xml" else {"id": f.stem, "segments": {}}
        witnesses.append(w)
    all_seg_ids = sorted({sid for w in witnesses for sid in w["segments"]})
    wit_ids = [w["id"] for w in witnesses]
    per_segment = {}
    for sid in all_seg_ids:
        per_segment[sid] = {}
        for wi in witnesses:
            per_segment[sid][wi["id"]] = {}
            for wj in witnesses:
                ta = wi["segments"].get(sid, "")
                tb = wj["segments"].get(sid, "")
                per_segment[sid][wi["id"]][wj["id"]] = {
                    "jaccard":      round(jaccard(ta, tb), 4),
                    "levenshtein":  round(levenshtein_norm(ta, tb), 4),
                }
    overall = {}
    for wi in witnesses:
        overall[wi["id"]] = {}
        for wj in witnesses:
            shared = [sid for sid in all_seg_ids if wi["segments"].get(sid) and wj["segments"].get(sid)]
            if not shared:
                overall[wi["id"]][wj["id"]] = {"jaccard": 0.0, "levenshtein": 0.0}
                continue
            overall[wi["id"]][wj["id"]] = {
                "jaccard":     round(sum(per_segment[s][wi["id"]][wj["id"]]["jaccard"]     for s in shared)/len(shared), 4),
                "levenshtein": round(sum(per_segment[s][wi["id"]][wj["id"]]["levenshtein"] for s in shared)/len(shared), 4),
            }
    return {"witnesses": wit_ids, "segments": all_seg_ids, "per_segment": per_segment, "overall": overall}

class CollateRequest(BaseModel):
    segment_id: str
    witness_ids: Optional[list[str]] = None

@app.post("/api/collate")
async def collate(req: CollateRequest):
    witnesses = []
    for f in list_witness_files():
        if f.stem.startswith("_"): continue
        w = parse_witness(f) if f.suffix == ".xml" else parse_plain(f)
        witnesses.append(w)
    if req.witness_ids:
        witnesses = [w for w in witnesses if w["id"] in req.witness_ids]
    tokens = [{"id": w["id"], "content": w["segments"].get(req.segment_id, "")}
              for w in witnesses if w["segments"].get(req.segment_id)]
    if len(tokens) < 2:
        raise HTTPException(400, "Need at least 2 witnesses with this segment")
    payload = {"witnesses": tokens, "algorithm": "dekker", "joined": True}
    result = collatex.collate(payload, segmentation=False, output="json")
    return Response(content=result, media_type="application/json")

@app.get("/api/stemma")
def get_stemma():
    data = get_matrix()
    wit_ids = data["witnesses"]
    overall = data["overall"]
    n = len(wit_ids)
    dist = [[1 - overall[wi][wj]["levenshtein"] for wj in wit_ids] for wi in wit_ids]
    clusters = [{"name": w, "children": [], "height": 0.0} for w in wit_ids]
    active = list(range(n))
    size = [1] * n
    while len(active) > 1:
        min_d, pi, pj = math.inf, -1, -1
        for ii in range(len(active)):
            for jj in range(ii+1, len(active)):
                if dist[active[ii]][active[jj]] < min_d:
                    min_d, pi, pj = dist[active[ii]][active[jj]], ii, jj
        i, j = active[pi], active[pj]
        merged = {"name": f"[{clusters[i]['name']}+{clusters[j]['name']}]",
                  "height": min_d/2, "children": [clusters[i], clusters[j]]}
        clusters.append(merged)
        new_idx = len(clusters)-1
        dist.append([0.0]*(new_idx+1))
        for k in range(new_idx): dist[k].append(0.0)
        for k in active:
            if k in (i,j): continue
            d = (dist[i][k]*size[i]+dist[j][k]*size[j])/(size[i]+size[j])
            dist[new_idx][k] = dist[k][new_idx] = d
        size.append(size[i]+size[j])
        active = [k for k in active if k not in (i,j)] + [new_idx]
    return {"tree": clusters[-1]}

# ── Upload endpoints ───────────────────────────────────────────────

@app.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    companion_csv: Optional[UploadFile] = File(None),
):
    """
    Step 1: Receive uploaded files, parse what we can, return metadata preview
    for the user to confirm/edit in the form.
    """
    # Parse companion CSV if provided
    csv_meta = {}
    if companion_csv:
        content = (await companion_csv.read()).decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            key = row.get("id", "").strip()
            if key:
                csv_meta[key] = {k: v.strip() for k, v in row.items() if k != "id"}

    previews = []
    for f in files:
        if f.filename.endswith("_metadata.json"): continue
        stem = Path(f.filename).stem
        content = await f.read()

        # Save to upload staging area
        dest = UPLOAD_DIR / f.filename
        dest.write_bytes(content)

        # Try to auto-detect metadata from TEI header
        auto = {"id": stem, "name": stem, "year": None, "country": "", "affiliation": "", "source": "", "lat": 0, "lng": 0}
        if f.filename.endswith(".xml"):
            try:
                root = ET.fromstring(content)
                ns = {"tei": TEI_NS}
                title_el   = root.find(".//tei:title",    ns)
                date_el    = root.find(".//tei:date",     ns)
                origin_el  = root.find(".//tei:pubPlace", ns)
                if title_el  is not None and title_el.text:  auto["name"]    = title_el.text.strip()
                if date_el   is not None:
                    yr = (date_el.get("when","") or date_el.text or "")[:4]
                    if yr.isdigit(): auto["year"] = int(yr)
                if origin_el is not None and origin_el.text: auto["country"] = origin_el.text.strip()

                # Count segments
                seg_count = sum(1 for tag in ("p","lg","l","ab")
                    for _ in root.findall(f".//tei:{tag}[@{{http://www.w3.org/XML/1998/namespace}}id]", ns))
                auto["segment_count"] = seg_count
            except Exception as e:
                auto["parse_error"] = str(e)
        elif f.filename.endswith(".txt"):
            lines = content.decode("utf-8").splitlines()
            auto["segment_count"] = sum(1 for l in lines if l.strip())

        # Merge with CSV metadata (CSV takes priority over auto-detected)
        if stem in csv_meta:
            auto.update({k: v for k, v in csv_meta[stem].items() if v})
            if "year" in csv_meta[stem] and csv_meta[stem]["year"].isdigit():
                auto["year"] = int(csv_meta[stem]["year"])

        previews.append(auto)

    return {"previews": previews, "csv_provided": companion_csv is not None}


class WitnessMetadata(BaseModel):
    id:          str
    name:        str
    year:        Optional[int]   = None
    country:     Optional[str]   = ""
    affiliation: Optional[str]   = ""
    source:      Optional[str]   = ""
    lat:         Optional[float] = 0.0
    lng:         Optional[float] = 0.0
    filename:    str  # original uploaded filename

class ConfirmRequest(BaseModel):
    witnesses: list[WitnessMetadata]
    replace:   bool = False  # if True, clear existing witnesses first

@app.post("/api/upload/confirm")
async def confirm_upload(req: ConfirmRequest):
    """
    Step 2: User has confirmed/edited metadata. Move files from staging to
    data dir, save metadata sidecar, return updated witness list.
    """
    if req.replace:
        for f in DATA_DIR.glob("*.xml"): f.unlink()
        for f in DATA_DIR.glob("*.txt"): f.unlink()
        # Wipe every stored score — the whole witness set is being replaced, so
        # all old seg_id keys are meaningless now.
        _scores_db.clear_all()

    meta = {}
    # Load existing metadata if not replacing
    meta_path = DATA_DIR / "_metadata.json"
    if not req.replace and meta_path.exists():
        meta = json.loads(meta_path.read_text())

    for w in req.witnesses:
        src = UPLOAD_DIR / w.filename
        if not src.exists():
            raise HTTPException(400, f"Staged file not found: {w.filename}")
        # Save the file named after the clean witness id (e.g. M1767.xml), not the
        # raw upload filename, so path.stem == w.id consistently across the backend.
        ext = ".xml" if w.filename.lower().endswith(".xml") else ".txt"
        safe_id = "".join(c for c in w.id if c.isalnum() or c in "-_") or w.filename
        dst = DATA_DIR / f"{safe_id}{ext}"
        shutil.copy2(src, dst)
        # A re-uploaded (or edited) witness must not keep scores from its previous
        # content: the same seg_id can now point at different text. Drop this
        # witness's stored pairs so nothing stale survives under identical keys.
        if not req.replace:
            _scores_db.delete_witness(safe_id)
        meta[w.id] = {
            "name":        w.name,
            "year":        w.year,
            "country":     w.country,
            "affiliation": w.affiliation,
            "source":      w.source,
            "lat":         w.lat,
            "lng":         w.lng,
        }

    _scores_db.commit()
    # The witness set changed, so the current alignment (segment positions,
    # relations, matrix) is stale. Forget it and its saved state; the user re-runs
    # alignment, and startup won't replay a run against a changed corpus.
    _reset_alignment_memory()
    _clear_align_state()

    meta_path.write_text(json.dumps(meta, indent=2))
    return {"status": "ok", "witnesses": req.witnesses}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Alignment ──────────────────────────────────────────────────────
# In-memory store of the most recent alignment run, keyed by witness id.
_ALIGN_CACHE: dict = {}
# "unit" is the segmentation label of the last run (from the --tags option, e.g.
# "p-lg"); "" means default line-level. It feeds the seg_id scheme below.
_ALIGN_ANCHOR: dict = {"id": None, "unit": "", "tags": []}

# Cache of parsed witness lines so each file is read from disk only once.
# Keyed by (witness id, tags tuple); value is (mtime, lines). Re-parses only if
# the file changed or a different set of segmentation tags is requested.
_LINES_CACHE: dict = {}

# All-pairs relation graph (#2), rebuilt on every alignment run.
#   _SEGMENTS[seg_id]  = {"wid", "pos", "n", "text"}   — every segment, all witnesses
#   _RELATIONS[seg_id] = [(other_seg_id, score), ...]  — cross-witness edges
_SEGMENTS: dict = {}
_RELATIONS: dict = {}
# Low keep-all threshold for FINDING relations. Not a display filter: callers
# filter by score at read time (#7). align-lab's default is 0.1.
REL_THRESHOLD = 0.1

# Default similarity floor for GROUPING segments into shared "reading" clusters
# (#9). Only edges at/above this score connect segments into a group, so a group
# means "confidently the same reading" rather than a loose chain. Exposed as a
# view-time parameter (min_score) so it can be tuned without re-running alignment.
GROUP_THRESHOLD = 0.45

from . import align_segments as _align
from .lab_similarity import Bundle, hybrid_score


def _make_seg_id(wid: str, unit: str, pos: int) -> str:
    """Intrinsic seg_id: "{wid}:{unit}:{pos}" with a segmentation unit, else
    "{wid}:{pos}". Single source of the scheme shared by the matrix, the relation
    graph, and the data-ids injected into served XML."""
    return f"{wid}:{unit}:{pos}" if unit else f"{wid}:{pos}"


def _compute_groups(min_score: float):
    """Cluster segments into shared "reading" groups (#9) from the relation graph.

    A reading group holds AT MOST ONE segment per witness — it represents "the same
    place across witnesses", not a chain of look-alike lines. We build groups
    greedily: consider the strongest edges first (score >= min_score) and merge the
    two segments' groups only if they don't already share a witness; a merge that
    would put two fragments of the same text together is rejected. This prevents the
    transitive-closure "hairball" that plain connected components produce on
    repetitive texts, so group size is bounded by the number of witnesses.

    Each group gets one stable id (a hash of its members) shared by every member, so
    clicking any fragment can highlight the whole reading across all texts. Singletons
    (no qualifying link) are omitted — they have no parallels. Returns:
      groups       = {group_id: [sorted seg_ids]}
      seg_to_group = {seg_id: group_id}
    min_score is a view-time knob (#7): nothing is deleted, we just re-partition the
    graph that already keeps every edge."""
    parent: dict = {}
    wits: dict = {}  # component root -> set of witness ids currently in that group

    def _wid(sid: str) -> str:
        seg = _SEGMENTS.get(sid)
        return seg["wid"] if seg else sid.rsplit(":", 1)[0]

    def find(x: str) -> str:
        if x not in parent:
            parent[x] = x
            wits[x] = {_wid(x)}
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(a: str, b: str):
        """Merge only if the two groups share no witness (one-per-witness rule)."""
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if wits[ra] & wits[rb]:
            return  # would collide two segments of the same witness — keep apart
        parent[ra] = rb
        wits[rb] |= wits[ra]
        wits.pop(ra, None)

    # Unique cross-witness edges at/above the threshold, strongest first, so the
    # most confident links claim their witness slot before weaker ones can.
    seen: set = set()
    edges: list = []
    for sid, elist in _RELATIONS.items():
        for other_id, score in elist:
            if score < min_score:
                continue
            key = (sid, other_id) if sid < other_id else (other_id, sid)
            if key in seen:
                continue
            seen.add(key)
            edges.append((score, key[0], key[1]))
    edges.sort(reverse=True)
    for _score, a, b in edges:
        union(a, b)

    comps: dict = {}
    for node in parent:
        comps.setdefault(find(node), []).append(node)

    groups: dict = {}
    seg_to_group: dict = {}
    for members in comps.values():
        if len(members) < 2:
            continue
        members = sorted(members)
        gid = "g" + hashlib.sha1(",".join(members).encode("utf-8")).hexdigest()[:12]
        groups[gid] = members
        for m in members:
            seg_to_group[m] = gid
    return groups, seg_to_group


# Sidecar holding the last alignment run's parameters. The alignment itself is
# reproducible from these + the witness files + the code, so on restart we replay
# the run instead of serializing the whole graph (which would risk going stale).
_ALIGN_STATE_PATH = DATA_DIR / "_align_state.json"


def _save_align_state(anchor_id: str, threshold: float, top_k: int, tag_list: list):
    _ALIGN_STATE_PATH.write_text(json.dumps({
        "anchor_id": anchor_id, "threshold": threshold,
        "top_k": top_k, "tags": tag_list,
    }))


def _clear_align_state():
    _ALIGN_STATE_PATH.unlink(missing_ok=True)


def _reset_alignment_memory():
    """Forget the current in-memory alignment (segments moved / files changed)."""
    _ALIGN_CACHE.clear()
    _SEGMENTS.clear()
    _RELATIONS.clear()
    _ALIGN_ANCHOR.update({"id": None, "unit": "", "tags": []})


def _load_lines_cached(path: Path, tags: list = None) -> list:
    """Load (and cache) the parsed segments for a witness file. `tags` (e.g.
    ['p', 'lg']) segments by those TEI tags; None/empty keeps line-level."""
    wid = path.stem
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    key = (wid, tuple(tags) if tags else ())
    cached = _LINES_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    lines = _align.load_witness(path, tags=tags)
    _LINES_CACHE[key] = (mtime, lines)
    return lines


@app.get("/api/align/witnesses")
def align_witnesses():
    """List witnesses available for alignment with their line counts."""
    result = []
    for f in sorted(DATA_DIR.glob("*.xml")) + sorted(DATA_DIR.glob("*.txt")):
        if f.stem.startswith("_"):
            continue
        try:
            lines = _load_lines_cached(f)
            result.append({"id": f.stem, "line_count": len(lines)})
        except Exception:
            result.append({"id": f.stem, "line_count": 0})
    # Sort by line count descending so the longest (suggested anchor) is first
    result.sort(key=lambda w: -w["line_count"])
    return result


class AlignRunRequest(BaseModel):
    anchor_id: str
    threshold: float = 0.35
    top_k: int = 15
    # Comma-separated TEI tags to use as segments (e.g. "p,lg"). Empty = lines.
    tags: str = ""


@app.post("/api/align/run")
def align_run(req: AlignRunRequest):
    """Run alignment of every witness against the chosen anchor, plus the all-pairs
    relation graph. Persists the run parameters so the alignment is restored after
    a restart (see _restore_last_alignment)."""
    # Segmentation tags: "p,lg" -> ['p','lg']; empty -> [] (default line-level).
    tag_list = [t.strip() for t in req.tags.split(",") if t.strip()]
    result = _run_alignment(req.anchor_id, req.threshold, req.top_k, tag_list)
    _save_align_state(req.anchor_id, req.threshold, req.top_k, tag_list)
    return result


def _run_alignment(anchor_id: str, threshold: float, top_k: int, tag_list: list) -> dict:
    """Core alignment: anchor pass (for the matrix view) + all-pairs relations.
    Shared by the /api/align/run endpoint and startup restore, so a replay
    reproduces the exact same in-memory state."""
    xml_path = DATA_DIR / f"{anchor_id}.xml"
    txt_path = DATA_DIR / f"{anchor_id}.txt"

    if xml_path.exists():
        unit = "-".join(tag_list)  # "" keeps the original "{wid}:{pos}" seg_id scheme
        anchor_lines = _load_lines_cached(xml_path, tags=tag_list)
    elif txt_path.exists():
        unit = ""
        anchor_lines = _load_lines_cached(txt_path, tags=[])
    else:
        raise HTTPException(404, f"Anchor {anchor_id} not found")
    if not anchor_lines:
        raise HTTPException(400, f"Anchor {anchor_id} has no readable segments")

    anchor_idx = _align.build_index(anchor_lines)
    anchor_sets = [Bundle(t) for (_n, t) in anchor_lines]  # built once, reused

    _ALIGN_CACHE.clear()
    _ALIGN_ANCHOR["id"] = anchor_id
    _ALIGN_ANCHOR["unit"] = unit
    _ALIGN_ANCHOR["tags"] = tag_list
    witnesses_stats = {}
    loaded_segments: dict = {}  # wid -> [(n, text), ...] in intrinsic pos order

    for f in sorted(DATA_DIR.glob("*.xml")) + sorted(DATA_DIR.glob("*.txt")):
        if f.stem.startswith("_"):
            continue
        wid = f.stem
        lines = _load_lines_cached(f, tags=tag_list)
        loaded_segments[wid] = lines
        if wid == anchor_id:
            # The anchor aligns perfectly to itself
            alignment = [
                {"witness_n": n, "witness_pos": i, "anchor_n": n, "anchor_pos": i,
                 "score": 1.0, "text": t, "anchor_text": t}
                for i, (n, t) in enumerate(anchor_lines)
            ]
        else:
            alignment = _align.align_witness(
                lines, anchor_lines, anchor_idx,
                threshold=threshold, top_k=top_k,
                anchor_sets=anchor_sets,
            )
        _ALIGN_CACHE[wid] = alignment
        witnesses_stats[wid] = _align.alignment_stats(alignment, threshold)

    # #2 — all-pairs cross-witness relations, independent of the anchor.
    n_edges = _build_relation_graph(loaded_segments, unit, top_k)

    return {
        "anchor_id": anchor_id,
        "threshold": threshold,
        "witnesses": witnesses_stats,
        "relations": n_edges,
    }


def _build_relation_graph(loaded_segments: dict, unit: str, top_k: int) -> int:
    """Build and persist the all-pairs relation graph (#2) for the given loaded
    witness segments. Rebuilds _SEGMENTS / _RELATIONS and upserts each edge's
    hybrid-Levenshtein score into the scores DB. Returns the edge count.

    Relations are found by Dice (keep-all at REL_THRESHOLD, transposition-tolerant
    one-to-one per pair); the stored/edge score is hybrid-Levenshtein, matching
    the pairwise score the matrix already uses so both views agree."""
    _SEGMENTS.clear()
    _RELATIONS.clear()

    bundles: dict = {}  # seg_id -> Bundle, memoised for hybrid scoring
    for wid, lines in loaded_segments.items():
        for pos, (n, text) in enumerate(lines):
            sid = _make_seg_id(wid, unit, pos)
            _SEGMENTS[sid] = {"wid": wid, "pos": pos, "n": n, "text": text}
            bundles[sid] = Bundle(text)

    edges = _align.build_relations(loaded_segments, threshold=REL_THRESHOLD, top_k=top_k)
    for wid_a, pos_a, wid_b, pos_b, _dice in edges:
        sa = _make_seg_id(wid_a, unit, pos_a)
        sb = _make_seg_id(wid_b, unit, pos_b)
        score = round(hybrid_score(bundles[sa], bundles[sb]), 4)
        _scores_db.upsert_score(sa, sb, score)
        _RELATIONS.setdefault(sa, []).append((sb, score))
        _RELATIONS.setdefault(sb, []).append((sa, score))
    _scores_db.commit()
    return len(edges)


@app.get("/api/align/inspect/{witness_id}")
def align_inspect(witness_id: str, limit: int = 100, offset: int = 0):
    """Return paginated alignment results for one witness."""
    if witness_id not in _ALIGN_CACHE:
        raise HTTPException(404, "No alignment found. Run alignment first.")
    alignment = _ALIGN_CACHE[witness_id]
    page = alignment[offset:offset + limit]
    return {
        "witness_id": witness_id,
        "anchor_id": _ALIGN_ANCHOR["id"],
        "total": len(alignment),
        "offset": offset,
        "limit": limit,
        "lines": page,
    }


@app.get("/api/align/matrix")
def align_matrix(max_rows: int = 0):
    """
    Return the most recent alignment as an anchor-indexed grid for the heatmap.
    Rows are anchor lines (in anchor order). For each row, every witness either
    has an aligned line (with its similarity score and text) or a gap (null).

    Shape:
    {
      "anchor_id": "BZ430",
      "witnesses": ["BZ430", "BZ449", ...],   # column order
      "anchor_lines": [{"n": 1, "text": "..."}, ...],
      "cells": {
         "BZ449": [ {"score": 0.55, "text": "..."} | null, ... ],  # one per anchor row
         ...
      }
    }
    max_rows: if > 0, cap the number of anchor rows returned (0 = all).
    """
    if not _ALIGN_CACHE or not _ALIGN_ANCHOR["id"]:
        raise HTTPException(400, "No alignment to read. Run alignment first.")
    anchor_id = _ALIGN_ANCHOR["id"]
    anchor_alignment = _ALIGN_CACHE.get(anchor_id, [])

    # Anchor rows, in order. Each anchor line is identified by its anchor_pos.
    anchor_lines = [{"n": a["witness_n"], "text": a["text"]} for a in anchor_alignment]
    n_rows = len(anchor_lines)
    if max_rows and n_rows > max_rows:
        n_rows = max_rows
        anchor_lines = anchor_lines[:n_rows]

    # seg_id scheme: "{wid}:{unit}:{pos}" when a segmentation unit is set (e.g.
    # "p-lg"), else "{wid}:{pos}". `pos` is the segment's INTRINSIC position in
    # its own text (0-based document order), not the anchor row it landed on — so
    # a segment keeps the same id whatever it aligns to, and whichever anchor is
    # chosen. Same string in the DOM data-id, the score keys, and the API — an
    # opaque, deterministic document-order id.
    unit = _ALIGN_ANCHOR.get("unit") or ""

    def _seg_id(wid: str, pos: int) -> str:
        return f"{wid}:{unit}:{pos}" if unit else f"{wid}:{pos}"

    witnesses = sorted(_ALIGN_CACHE.keys())
    cells = {}
    for wid in witnesses:
        row = [None] * n_rows
        if wid == anchor_id:
            for pos in range(n_rows):
                row[pos] = {"score": 1.0, "text": anchor_alignment[pos]["text"],
                            "seg_id": _seg_id(wid, pos)}
        else:
            for a in _ALIGN_CACHE[wid]:
                pos = a.get("anchor_pos")
                if pos is not None and pos < n_rows:
                    # Keep the best-scoring witness line if several map here
                    prev = row[pos]
                    if prev is None or a["score"] > prev["score"]:
                        row[pos] = {"score": a["score"], "text": a["text"],
                                    "seg_id": _seg_id(wid, a["witness_pos"])}
        cells[wid] = row

    # Hybrid-Levenshtein pairwise scoring: for every anchor row, score every
    # pair of witnesses that both land on that row, keyed by their seg_ids.
    for pos in range(n_rows):
        occupants = [(wid, cells[wid][pos]) for wid in witnesses if cells[wid][pos] is not None]
        for i in range(len(occupants)):
            wid_a, cell_a = occupants[i]
            bundle_a = Bundle(cell_a["text"])
            for j in range(i + 1, len(occupants)):
                wid_b, cell_b = occupants[j]
                score = hybrid_score(bundle_a, Bundle(cell_b["text"]))
                _scores_db.upsert_score(cell_a["seg_id"], cell_b["seg_id"], round(score, 4))
    _scores_db.commit()

    return {
        "anchor_id": anchor_id,
        "witnesses": witnesses,
        "anchor_lines": anchor_lines,
        "cells": cells,
    }


@app.get("/api/align/score")
def align_score(seg_a: str, seg_b: str):
    """Look up the stored hybrid-Levenshtein score for a pair of segment IDs
    (intrinsic scheme: "{witness_id}:{pos}", or "{witness_id}:{unit}:{pos}" when a
    segmentation unit was used), as computed by the alignment run / matrix."""
    score = _scores_db.get_score(seg_a, seg_b)
    if score is None:
        raise HTTPException(404, "No stored score for this segment pair.")
    return {"seg_a": seg_a, "seg_b": seg_b, "score": score}


@app.get("/api/align/related")
def align_related(seg_id: str, min_score: float = 0.0):
    """Related segments in OTHER witnesses for a given segment, from the all-pairs
    relation graph (#2). Returns them sorted by score (highest first), optionally
    filtered to score >= min_score (a display filter, #7 — the graph itself keeps
    everything). Requires a prior /api/align/run."""
    if not _SEGMENTS:
        raise HTTPException(400, "No relations available. Run alignment first.")
    seg = _SEGMENTS.get(seg_id)
    if seg is None:
        raise HTTPException(404, f"Unknown segment {seg_id}.")
    related = []
    for other_id, score in sorted(_RELATIONS.get(seg_id, []), key=lambda x: -x[1]):
        if score < min_score:
            continue
        other = _SEGMENTS.get(other_id, {})
        related.append({
            "seg_id":  other_id,
            "witness": other.get("wid"),
            "n":       other.get("n"),
            "text":    other.get("text"),
            "score":   score,
        })
    return {
        "seg_id":  seg_id,
        "witness": seg["wid"],
        "n":       seg["n"],
        "text":    seg["text"],
        "related": related,
    }


@app.get("/api/align/groups")
def align_groups(min_score: float = GROUP_THRESHOLD):
    """Shared "reading" groups across all witnesses (#9). Clusters segments into
    connected components over relation edges with score >= min_score, giving each
    group one id that every member shares — so clicking any fragment can highlight
    the whole reading in every text (Option B). min_score is a view-time knob (#7):
    raise it for tighter, more confident groups; lower it to merge weaker matches.
    Returns groups (id -> member seg_ids) and seg_to_group (seg_id -> id).
    Requires a prior /api/align/run."""
    if not _SEGMENTS:
        raise HTTPException(400, "No relations available. Run alignment first.")
    groups, seg_to_group = _compute_groups(min_score)
    return {
        "min_score":    min_score,
        "count":        len(groups),
        "groups":       groups,
        "seg_to_group": seg_to_group,
    }


@app.get("/api/align/witnesses/{witness_id}/scores")
def align_witness_scores(witness_id: str):
    """All pairwise scores for every segment in one witness, in a single response.

    Returns each segment of `witness_id` with the full list of cross-witness
    matches and their scores (sourced from the in-memory relation graph, same
    data as /api/align/related but batched by witness). The frontend can:
      - compute an average score per segment for background colouring (no
        reference text needed);
      - recompute that average on the fly when witnesses are hidden, by
        filtering the returned `scores` list to only visible witness ids.
    Requires a prior /api/align/run."""
    if not _SEGMENTS:
        raise HTTPException(400, "No relations available. Run alignment first.")
    segments = [
        (seg_id, meta)
        for seg_id, meta in _SEGMENTS.items()
        if meta["wid"] == witness_id
    ]
    if not segments:
        raise HTTPException(404, f"No segments found for witness '{witness_id}'. "
                                 "Check the witness id or run alignment first.")
    segments.sort(key=lambda x: x[1]["pos"])
    result = []
    for seg_id, meta in segments:
        scores = [
            {"seg_id": other_id, "witness": _SEGMENTS[other_id]["wid"], "score": score}
            for other_id, score in _RELATIONS.get(seg_id, [])
            if other_id in _SEGMENTS
        ]
        scores.sort(key=lambda x: -x["score"])
        result.append({
            "seg_id": seg_id,
            "n":      meta["n"],
            "text":   meta["text"],
            "scores": scores,
        })
    return {"witness_id": witness_id, "segments": result}


@app.post("/api/align/save")
def align_save():
    """Write augmented TEI files for the most recent alignment run."""
    if not _ALIGN_CACHE or not _ALIGN_ANCHOR["id"]:
        raise HTTPException(400, "No alignment to save. Run alignment first.")
    out_dir = DATA_DIR / "_augmented"
    out_dir.mkdir(exist_ok=True)
    count = 0
    for wid, alignment in _ALIGN_CACHE.items():
        src = DATA_DIR / f"{wid}.xml"
        if not src.exists():
            continue
        dest = out_dir / f"{wid}.xml"
        try:
            _align.save_augmented_tei(src, dest, alignment, wid)
            count += 1
        except Exception:
            pass
    return {"status": "ok", "count": count, "dir": str(out_dir)}


# ── Restore last alignment on startup ──────────────────────────────
def _restore_last_alignment():
    """Replay the last alignment run (parameters saved in _align_state.json) so
    the in-memory alignment — segments, relations, matrix — is back after a
    restart, and the persisted scores are addressable rather than orphaned.
    Best-effort: skipped silently if there's no saved run or the anchor is gone."""
    if not _ALIGN_STATE_PATH.exists():
        return
    try:
        st = json.loads(_ALIGN_STATE_PATH.read_text())
        if not (DATA_DIR / f"{st['anchor_id']}.xml").exists():
            return
        _run_alignment(st["anchor_id"], st.get("threshold", 0.35),
                       st.get("top_k", 15), st.get("tags", []))
    except Exception:
        pass


_restore_last_alignment()
