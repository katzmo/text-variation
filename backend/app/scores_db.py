"""scores_db.py — lightest possible persistence for pairwise segment scores.

Stores hybrid-Levenshtein scores keyed by an unordered pair of segment IDs
(scheme: "{witness_id}:{anchor_pos}"), so the collation view can look up the
score for any two aligned segments.
"""
import sqlite3
from pathlib import Path

_conn: sqlite3.Connection | None = None


def init_db(data_dir: Path):
    global _conn
    db_path = data_dir / "_scores.db"
    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS pair_scores (
               seg_a TEXT NOT NULL,
               seg_b TEXT NOT NULL,
               score REAL NOT NULL,
               PRIMARY KEY (seg_a, seg_b)
           )"""
    )
    _conn.commit()


def _order(seg_a: str, seg_b: str):
    return (seg_a, seg_b) if seg_a <= seg_b else (seg_b, seg_a)


def upsert_score(seg_a: str, seg_b: str, score: float):
    a, b = _order(seg_a, seg_b)
    _conn.execute(
        "INSERT OR REPLACE INTO pair_scores (seg_a, seg_b, score) VALUES (?, ?, ?)",
        (a, b, score),
    )


def commit():
    _conn.commit()


def get_score(seg_a: str, seg_b: str):
    a, b = _order(seg_a, seg_b)
    row = _conn.execute(
        "SELECT score FROM pair_scores WHERE seg_a = ? AND seg_b = ?", (a, b)
    ).fetchone()
    return row[0] if row else None


def delete_witness(wid: str):
    """Remove every stored pair that references a segment of this witness, so a
    re-uploaded file doesn't leave misleading scores under identical seg_id keys.
    seg_ids follow "{wid}:..." — matched with GLOB, whose only metacharacters
    (* ? [) never occur in a witness id (alphanumeric / - / _)."""
    pat = f"{wid}:*"
    _conn.execute(
        "DELETE FROM pair_scores WHERE seg_a GLOB ? OR seg_b GLOB ?", (pat, pat)
    )


def clear_all():
    """Drop all stored scores (used when an upload replaces the whole witness set)."""
    _conn.execute("DELETE FROM pair_scores")
