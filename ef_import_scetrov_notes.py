#!/usr/bin/env python3
"""
Import Scetrov community notes into site.db.

If sources/scetrov_notes.jsonl exists, import it directly.
If missing, run ef_fetch_scetrov_notes.py to generate it first.

Usage:
  python ef_import_scetrov_notes.py
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

JSONL_PATH = Path("sources") / "scetrov_notes.jsonl"
DB_PATH = Path("site.db")
FETCH_SCRIPT = Path("ef_fetch_scetrov_notes.py")


def clean_title(raw: str) -> str:
    """Strip the ':: Unofficial EVE Frontier Development Notes' suffix."""
    if " :: " in raw:
        return raw.split(" :: ")[0].strip()
    return raw.strip()


def ensure_jsonl() -> bool:
    """Ensure sources/scetrov_notes.jsonl exists. Returns True on success."""
    if JSONL_PATH.exists():
        return True

    if not FETCH_SCRIPT.exists():
        print(f"SCETROV_IMPORT_FAILED: Fetch script not found at {FETCH_SCRIPT}")
        print("records_imported: 0")
        return False

    print(f"sources/scetrov_notes.jsonl not found, running {FETCH_SCRIPT}...")
    result = subprocess.run(
        ["python", str(FETCH_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=650,
    )
    # Print fetch output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0 or not JSONL_PATH.exists():
        print("SCETROV_IMPORT_FAILED: Fetch step failed")
        print(f"reason: exit_code={result.returncode}")
        print("records_imported: 0")
        return False

    return True


def main() -> int:
    if not ensure_jsonl():
        return 0  # Non-fatal, but failure was logged

    if not DB_PATH.exists():
        print("site.db not found, run ef_import_site_db.py first")
        return 1

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    inserted = 0
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
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
                    rec.get("slug_id", ""),
                    rec.get("source", ""),
                    rec.get("authority_tier", ""),
                    rec.get("url", ""),
                    rec.get("path", ""),
                    rec.get("title", ""),
                    rec.get("content_sha256", ""),
                    rec.get("retrieved_at", ""),
                    rec.get("text", ""),
                    rec.get("raw_text", ""),
                    rec.get("source_repo", ""),
                    rec.get("source_commit", ""),
                    rec.get("source_ref", ""),
                    rec.get("file_extension", ""),
                    rec.get("size_bytes", 0),
                    rec.get("permission_status", ""),
                    rec.get("environment", "n/a"),
                    rec.get("chain_environment", "n/a"),
                    rec.get("source_status", "community"),
                    rec.get("production_relevance", "reference"),
                ),
            )

            for cat in rec.get("source_categories", []):
                db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

            # Add per-page section as an additional queryable category
            section = rec.get("section", "")
            if section:
                db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, section))

            for h in rec.get("headings", []):
                db.execute(
                    "INSERT INTO record_headings (record_id, level, text) VALUES (?, ?, ?)",
                    (rid, h.get("level", 0), h.get("text", "")),
                )

            for u in rec.get("outlinks", []):
                db.execute("INSERT INTO record_outlinks (record_id, url) VALUES (?, ?)", (rid, u))

            inserted += 1

    db.commit()

    # Rebuild FTS
    db.execute("INSERT INTO records_fts(records_fts) VALUES ('rebuild')")
    db.commit()

    print(f"Imported {inserted} Scetrov community notes into site.db")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
