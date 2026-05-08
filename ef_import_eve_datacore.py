#!/usr/bin/env python3
"""
Import EVE Datacore as a community reference entry into site.db.

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


def main() -> int:
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    rec = {
        "id": "community/eve-datacore",
        "slug_id": "",
        "source": "eve_datacore",
        "authority_tier": "community_reference",
        "url": "https://evedataco.re/",
        "path": "/",
        "title": "EVE Datacore",
        "content_sha256": "",
        "retrieved_at": "",
        "text": (
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
        ),
        "raw_text": "",
        "source_repo": "",
        "source_commit": "",
        "source_ref": "",
        "file_extension": "html",
        "size_bytes": 0,
        "permission_status": "publicly_accessible",
        "source_categories": ["static-data", "game-data", "items", "world-data", "tools", "explorers"],
        "headings": [],
        "outlinks": ["https://evedataco.re/"],
    }

    # Compute hash
    rec["content_sha256"] = hashlib.sha256(rec["text"].encode()).hexdigest()
    rec["size_bytes"] = len(rec["text"].encode())

    # Write JSONL
    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {JSONL_PATH}")

    # Import into site.db
    if not DB_PATH.exists():
        print("site.db not found, run ef_import_site_db.py first")
        return 1

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

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
            permission_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            rec["raw_text"],
            rec["source_repo"],
            rec["source_commit"],
            rec["source_ref"],
            rec["file_extension"],
            rec["size_bytes"],
            rec["permission_status"],
        ),
    )

    for cat in rec["source_categories"]:
        db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

    for u in rec["outlinks"]:
        db.execute("INSERT INTO record_outlinks (record_id, url) VALUES (?, ?)", (rid, u))

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

    print(f"Imported EVE Datacore into site.db")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
