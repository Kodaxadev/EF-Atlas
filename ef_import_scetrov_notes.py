#!/usr/bin/env python3
"""
Import Scetrov community notes CSV into JSONL and append to site.db.

Usage:
  python ef_import_scetrov_notes.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

CSV_PATH = Path.home() / "Downloads" / "frontier-site-knowledge-matrix.csv"
JSONL_PATH = Path("sources") / "scetrov_notes.jsonl"
DB_PATH = Path("site.db")


def clean_title(raw: str) -> str:
    """Strip the ':: Unofficial EVE Frontier Development Notes' suffix."""
    if " :: " in raw:
        return raw.split(" :: ")[0].strip()
    return raw.strip()


def path_to_id(path: str) -> str:
    """Convert a site path like /develop/world-api/ to scetrov/develop/world-api."""
    p = path.strip("/")
    # Remove trailing //
    p = p.rstrip("/").rstrip("/")
    if not p:
        p = "home"
    return f"scetrov/{p}"


def parse_pipe_list(value: str) -> list[str]:
    """Split a pipe-separated string into a cleaned list."""
    if not value:
        return []
    return [x.strip() for x in value.split("|") if x.strip()]


def headings_to_struct(raw: str) -> list[dict]:
    """Convert 'Heading1 | Heading2 | Heading3' into [{level: 1, text: ...}]."""
    parts = parse_pipe_list(raw)
    result = []
    for part in parts:
        # Headings are plain text; assign level 1 by default
        result.append({"level": 1, "text": part})
    return result


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return 1

    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    seen_ids = set()
    count = 0

    with open(CSV_PATH, "r", encoding="utf-8") as csvf, \
         open(JSONL_PATH, "w", encoding="utf-8") as jsonlf:

        reader = csv.DictReader(csvf)
        for row in reader:
            section = row.get("section", "").strip()
            if section == "home":
                continue

            rid = path_to_id(row.get("path", ""))
            if rid in seen_ids:
                continue
            seen_ids.add(rid)

            title = clean_title(row.get("title", ""))
            summary = row.get("summary", "").strip()

            rec = {
                "id": rid,
                "slug_id": "",
                "source": "scetrov_frontier_notes",
                "authority_tier": "community_reference",
                "url": row.get("url", "").strip(),
                "path": row.get("path", "").strip(),
                "title": title,
                "content_sha256": hashlib.sha256(title.encode() + summary.encode()).hexdigest(),
                "retrieved_at": "",
                "text": summary,
                "raw_text": summary,
                "source_repo": "https://github.com/Scetrov/frontier.scetrov.live",
                "source_commit": "",
                "source_ref": "",
                "file_extension": "md",
                "size_bytes": len(summary.encode()),
                "source_categories": [section],
                "headings": headings_to_struct(row.get("headings", "")),
                "outlinks": parse_pipe_list(row.get("sample_external_links", "")),
            }

            jsonlf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} records to {JSONL_PATH}")

    # Append to site.db using ef_import_site_db logic
    import sqlite3
    from pathlib import Path as P

    db_path = P("site.db")
    if not db_path.exists():
        print("site.db not found, run ef_import_site_db.py first")
        return 1

    db = sqlite3.connect(str(db_path))
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
                    source_repo, source_commit, source_ref, file_extension, size_bytes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                ),
            )

            for cat in rec.get("source_categories", []):
                db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

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

    # Stats
    row = db.execute("SELECT COUNT(*) FROM records").fetchone()
    print(f"Total records in DB: {row[0]}")
    row = db.execute("SELECT authority_tier, COUNT(*) FROM records GROUP BY authority_tier ORDER BY COUNT(*) DESC").fetchall()
    for tier, cnt in row:
        print(f"  {tier}: {cnt}")

    print(f"Imported {inserted} Scetrov community notes into site.db")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
