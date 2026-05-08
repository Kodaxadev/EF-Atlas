#!/usr/bin/env python3
"""
Import EVE Datacore as a community reference entry into site.db.

If sources/eve_datacore.jsonl exists, use it.
If missing, generate the record in memory and import directly.

Usage:
  python ef_import_eve_datacore.py
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

JSONL_PATH = Path("sources") / "eve_datacore.jsonl"
DB_PATH = Path("site.db")


def build_datacore_record() -> dict:
    """Build the EVE Datacore record in memory."""
    text = (
        "EVE Datacore is a community-run reference site for navigating and understanding "
        "the universe of EVE Frontier. It provides browsing access to static game data, "
        "item/type lookups, world and object references, and builder discovery of available entities.\n\n"
        "Useful for:\n"
        "- Item/type lookup\n"
        "- Static game data browsing\n"
        "- World/object references\n"
        "- Cross-checking client/static data\n"
        "- Builder discovery of available entities\n\n"
        "Not sufficient for:\n"
        "- Contract logic truth\n"
        "- Official package IDs\n"
        "- Registry schema\n"
        "- Policy/enforcement claims\n\n"
        "Good search terms: EVE Datacore, item types, static data, world data, "
        "EVE Frontier database, resources, assemblies, gates, systems."
    )
    rec = {
        "id": "community/eve-datacore",
        "slug_id": "",
        "source": "eve_datacore",
        "authority_tier": "community_reference",
        "url": "https://evedataco.re/",
        "path": "/",
        "title": "EVE Datacore",
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "retrieved_at": "",
        "text": text,
        "raw_text": "",
        "source_repo": "",
        "source_commit": "",
        "source_ref": "",
        "file_extension": "html",
        "size_bytes": len(text.encode()),
        "permission_status": "publicly_accessible",
        "source_categories": ["static-data", "game-data", "items", "world-data", "tools", "explorers"],
        "headings": [],
        "outlinks": ["https://evedataco.re/"],
    }
    return rec


def ensure_jsonl() -> bool:
    """Ensure sources/eve_datacore.jsonl exists. Returns True on success."""
    if JSONL_PATH.exists():
        return True

    # Generate in memory
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    rec = build_datacore_record()
    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Generated {JSONL_PATH} in memory")
    return True


def main() -> int:
    if not ensure_jsonl():
        print("WARNING: Could not generate EVE Datacore record")
        return 0  # Non-fatal

    if not DB_PATH.exists():
        print("site.db not found, run ef_import_site_db.py first")
        return 1

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

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
                    "n/a",
                    "n/a",
                    "community",
                    "reference",
                ),
            )

            for cat in rec.get("source_categories", []):
                db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

            for u in rec.get("outlinks", []):
                db.execute("INSERT INTO record_outlinks (record_id, url) VALUES (?, ?)", (rid, u))

    db.commit()

    # Rebuild FTS
    db.execute("INSERT INTO records_fts(records_fts) VALUES ('rebuild')")
    db.commit()

    print("Imported EVE Datacore into site.db")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
