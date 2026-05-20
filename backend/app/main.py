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
  POST /api/align/save          → write augmented TEI files
"""

import os, json, math, csv, io, shutil
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import httpx

# ── paths ──────────────────────────────────────────────────────────
DATA_DIR     = Path(os.getenv("DATA_DIR",     "/app/data/witnesses"))
UPLOAD_DIR   = Path(os.getenv("UPLOAD_DIR",   "/app/data/uploads"))
COLLATEX_URL = os.getenv("COLLATEX_URL", "http://collatex:7369/collatex/collate")
TEI_NS       = "http://www.tei-c.org/ns/1.0"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="kat-text-tool API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── TEI parsing ────────────────────────────────────────────────────

def parse_witness(path: Path) -> dict:
    tree = ET.parse(path)
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
        "year":     int(date_el.get("when", date_el.text or "0")[:4])
                    if date_el is not None else None,
        "origin":   origin_el.text if origin_el is not None else None,
        "segments": segments,
    }

def parse_plain(path: Path) -> dict:
    """Parse plain text: each non-empty line is a segment."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    segments = {f"seg-{str(i+1).padStart(3,'0')}": l for i, l in enumerate(lines)}
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
    for ext in (".xml", ".txt"):
        path = DATA_DIR / f"{witness_id}{ext}"
        if path.exists():
            mt = "application/xml" if ext == ".xml" else "text/plain"
            return Response(content=path.read_text(), media_type=mt)
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
        w = parse_witness(f) if f.suffix == ".xml" else {"id": f.stem, "segments": {}}
        witnesses.append(w)
    if req.witness_ids:
        witnesses = [w for w in witnesses if w["id"] in req.witness_ids]
    tokens = [{"id": w["id"], "content": w["segments"].get(req.segment_id, "")}
              for w in witnesses if w["segments"].get(req.segment_id)]
    if len(tokens) < 2:
        raise HTTPException(400, "Need at least 2 witnesses with this segment")
    payload = {"witnesses": tokens, "algorithm": "dekker", "joined": True}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(COLLATEX_URL, json=payload, headers={"Accept": "application/json"})
            r.raise_for_status()
            return r.json()
    except Exception:
        return _mock_alignment(tokens)

def _mock_alignment(tokens):
    all_words = [t["content"].split() for t in tokens]
    max_len = max(len(w) for w in all_words)
    table = []
    for i in range(max_len):
        row = {}
        for j, t in enumerate(tokens):
            row[t["id"]] = [{"t": all_words[j][i], "n": all_words[j][i].lower()}] if i < len(all_words[j]) else [{"t": "", "n": ""}]
        table.append(row)
    return {"table": table, "witnesses": [t["id"] for t in tokens]}

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
        meta[w.id] = {
            "name":        w.name,
            "year":        w.year,
            "country":     w.country,
            "affiliation": w.affiliation,
            "source":      w.source,
            "lat":         w.lat,
            "lng":         w.lng,
        }

    meta_path.write_text(json.dumps(meta, indent=2))
    return {"status": "ok", "witnesses": req.witnesses}


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Alignment ──────────────────────────────────────────────────────
# In-memory store of the most recent alignment run, keyed by witness id.
_ALIGN_CACHE: dict = {}
_ALIGN_ANCHOR: dict = {"id": None}

# Cache of parsed witness lines so each file is read from disk only once.
# Keyed by witness id; value is (mtime, lines). Re-parses only if the file changed.
_LINES_CACHE: dict = {}

from . import align_segments as _align


def _load_lines_cached(path: Path) -> list:
    """Load (and cache) the parsed lines for a witness file."""
    wid = path.stem
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    cached = _LINES_CACHE.get(wid)
    if cached and cached[0] == mtime:
        return cached[1]
    lines = _align.load_witness(path)
    _LINES_CACHE[wid] = (mtime, lines)
    return lines


@app.get("/api/align/witnesses")
def align_witnesses():
    """List witnesses available for alignment with their line counts."""
    result = []
    for f in sorted(DATA_DIR.glob("*.xml")):
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


@app.post("/api/align/run")
def align_run(req: AlignRunRequest):
    """Run alignment of every witness against the chosen anchor."""
    anchor_path = DATA_DIR / f"{req.anchor_id}.xml"
    if not anchor_path.exists():
        raise HTTPException(404, f"Anchor {req.anchor_id} not found")

    anchor_lines = _load_lines_cached(anchor_path)
    if not anchor_lines:
        raise HTTPException(400, f"Anchor {req.anchor_id} has no readable lines")
    anchor_idx = _align.build_index(anchor_lines)
    anchor_sets = [set(t.split()) for (_n, t) in anchor_lines]  # built once, reused

    _ALIGN_CACHE.clear()
    _ALIGN_ANCHOR["id"] = req.anchor_id
    witnesses_stats = {}

    for f in sorted(DATA_DIR.glob("*.xml")):
        if f.stem.startswith("_"):
            continue
        wid = f.stem
        if wid == req.anchor_id:
            # The anchor aligns perfectly to itself
            alignment = [
                {"witness_n": n, "anchor_n": n, "anchor_pos": i,
                 "score": 1.0, "text": t, "anchor_text": t}
                for i, (n, t) in enumerate(anchor_lines)
            ]
        else:
            lines = _load_lines_cached(f)
            alignment = _align.align_witness(
                lines, anchor_lines, anchor_idx,
                threshold=req.threshold, top_k=req.top_k,
                anchor_sets=anchor_sets,
            )
        _ALIGN_CACHE[wid] = alignment
        witnesses_stats[wid] = _align.alignment_stats(alignment, req.threshold)

    return {
        "anchor_id": req.anchor_id,
        "threshold": req.threshold,
        "witnesses": witnesses_stats,
    }


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

    witnesses = sorted(_ALIGN_CACHE.keys())
    cells = {}
    for wid in witnesses:
        row = [None] * n_rows
        if wid == anchor_id:
            for pos in range(n_rows):
                row[pos] = {"score": 1.0, "text": anchor_alignment[pos]["text"]}
        else:
            for a in _ALIGN_CACHE[wid]:
                pos = a.get("anchor_pos")
                if pos is not None and pos < n_rows:
                    # Keep the best-scoring witness line if several map here
                    prev = row[pos]
                    if prev is None or a["score"] > prev["score"]:
                        row[pos] = {"score": a["score"], "text": a["text"]}
        cells[wid] = row

    return {
        "anchor_id": anchor_id,
        "witnesses": witnesses,
        "anchor_lines": anchor_lines,
        "cells": cells,
    }


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

