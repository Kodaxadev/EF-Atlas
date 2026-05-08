#!/usr/bin/env python3
"""
Import Atlas watch notes into site.db as queryable records.

Usage:
  python ef_import_watch_notes.py

Reads watch notes from out/synthesis/watch_notes.md and inserts as official_tooling records.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict

DB_PATH = Path("site.db")
WATCH_PATH = Path("out") / "synthesis" / "watch_notes.md"

SCHEMA_ADDITIONS = """
CREATE TABLE IF NOT EXISTS watch_notes (
    id TEXT PRIMARY KEY,
    title TEXT,
    body TEXT,
    source TEXT,
    authority_tier TEXT,
    change_type TEXT,
    retrieved_at TEXT,
    content_sha256 TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def parse_watch_notes(path: Path) -> list[Dict[str, Any]]:
    """Parse watch_notes.md into individual note records."""
    if not path.exists():
        print(f"Watch notes file not found: {path}")
        return []

    text = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # Extract metadata from frontmatter-like section (handle **key:** format)
    meta: Dict[str, str] = {}
    title = "Atlas Watch Note"
    for line in text.splitlines()[:12]:
        # H1 heading as title
        if line.startswith("# "):
            title = line[2:].strip()
        # **key:** value pairs (colon inside bold markers)
        m = re.match(r"^\*\*(\w+):\*\*\s*(.+)$", line)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()

    source = "atlas_watch"
    authority_tier = "official_tooling"
    change_type = meta.get("change_type", "watch_note")
    retrieved_at = meta.get("retrieved_at", "")
    categories_str = meta.get("categories", "")
    categories = [c.strip() for c in categories_str.split(",") if c.strip()]

    record_id = f"watch:{hashlib.sha256(title.encode()).hexdigest()[:12]}"

    return [
        {
            "id": record_id,
            "slug_id": f"watch:{title.lower().replace(' ', '-')[:40]}",
            "source": source,
            "authority_tier": authority_tier,
            "url": f"atlas://watch/{record_id}",
            "path": "/watch",
            "title": title,
            "content_sha256": content_hash,
            "retrieved_at": retrieved_at,
            "text": text,
            "raw_markdown": text,
            "source_categories": ["watch"] + categories,
            "source_repo": "",
            "source_commit": "",
            "source_ref": "",
            "file_extension": ".md",
            "size_bytes": len(text.encode("utf-8")),
            "permission_status": "",
            "environment": "n/a",
            "chain_environment": "n/a",
            "source_status": "current",
            "production_relevance": "watch",
            "headings": [],
            "outlinks": [],
        }
    ]


def import_watch_note(db: sqlite3.Connection, rec: Dict[str, Any]) -> None:
    """Insert a watch note record into the database."""
    rid = rec["id"]

    # Upsert
    db.execute("DELETE FROM record_outlinks WHERE record_id = ?", (rid,))
    db.execute("DELETE FROM record_headings WHERE record_id = ?", (rid,))
    db.execute("DELETE FROM record_categories WHERE record_id = ?", (rid,))
    db.execute("DELETE FROM records WHERE id = ?", (rid,))

    db.execute(
        """INSERT INTO records
           (id, slug_id, source, authority_tier, url, path, title,
            content_sha256, retrieved_at, text, raw_text,
            source_repo, source_commit, source_ref, file_extension, size_bytes,
            permission_status, environment, chain_environment, source_status,
            production_relevance)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rid,
            rec["slug_id"],
            rec["source"],
            rec["authority_tier"],
            rec["url"],
            rec["path"],
            rec["title"],
            rec["content_sha256"],
            rec["retrieved_at"],
            rec["text"],
            rec["raw_markdown"],
            rec["source_repo"],
            rec["source_commit"],
            rec["source_ref"],
            rec["file_extension"],
            rec["size_bytes"],
            rec["permission_status"],
            rec["environment"],
            rec["chain_environment"],
            rec["source_status"],
            rec["production_relevance"],
        ),
    )

    # Categories
    for cat in rec["source_categories"]:
        db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

    # Headings
    for h in rec["headings"]:
        if isinstance(h, dict):
            db.execute(
                "INSERT INTO record_headings (record_id, level, text) VALUES (?, ?, ?)",
                (rid, h.get("level", 0), h.get("text", "")),
            )

    # Outlinks
    for u in rec["outlinks"]:
        db.execute("INSERT INTO record_outlinks (record_id, url) VALUES (?, ?)", (rid, u))

    db.commit()


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}. Run ef_import_site_db.py first.")
        return 1

    notes = parse_watch_notes(WATCH_PATH)
    if not notes:
        print("No watch notes to import.")
        return 0

    db = get_db()
    for note in notes:
        import_watch_note(db, note)
        print(f"Imported watch note: {note['title']} (id={note['id']})")

    # Verify
    row = db.execute(
        "SELECT id, title, authority_tier, source FROM records WHERE source = 'atlas_watch'"
    ).fetchall()
    print(f"\nTotal watch notes in DB: {len(row)}")
    for r in row:
        print(f"  {r['title']} | {r['authority_tier']} | {r['source']}")

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
