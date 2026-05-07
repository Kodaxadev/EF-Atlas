"""Database helpers for the EF Knowledge Atlas site."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("site.db")


def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db


def search(
    db: sqlite3.Connection,
    query: str = "",
    authority: str = "",
    category: str = "",
    source: str = "",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conditions = []
    params: list = []

    if query.strip():
        # FTS search
        fts_query = query.strip().replace('"', '""')
        conditions.append("r.rowid IN (SELECT rowid FROM records_fts WHERE records_fts MATCH ?)")
        params.append(fts_query)
    else:
        # No query: just filter
        pass

    if authority:
        conditions.append("r.authority_tier = ?")
        params.append(authority)
    if category:
        conditions.append("r.id IN (SELECT record_id FROM record_categories WHERE category = ?)")
        params.append(category)
    if source:
        conditions.append("r.source = ?")
        params.append(source)

    where = " AND ".join(conditions) if conditions else "1"
    sql = f"""
        SELECT r.*, 
               GROUP_CONCAT(DISTINCT rc.category) as categories
        FROM records r
        LEFT JOIN record_categories rc ON r.id = rc.record_id
        WHERE {where}
        GROUP BY r.id
        ORDER BY 
            CASE r.authority_tier
                WHEN 'authoritative_source' THEN 1
                WHEN 'official_docs' THEN 2
                WHEN 'official_tooling' THEN 3
                WHEN 'installed_client_observation' THEN 4
                WHEN 'community_reference' THEN 5
                ELSE 6
            END,
            r.title
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_search(
    db: sqlite3.Connection,
    query: str = "",
    authority: str = "",
    category: str = "",
    source: str = "",
) -> int:
    conditions = []
    params: list = []

    if query.strip():
        fts_query = query.strip().replace('"', '""')
        conditions.append("r.rowid IN (SELECT rowid FROM records_fts WHERE records_fts MATCH ?)")
        params.append(fts_query)
    if authority:
        conditions.append("r.authority_tier = ?")
        params.append(authority)
    if category:
        conditions.append("r.id IN (SELECT record_id FROM record_categories WHERE category = ?)")
        params.append(category)
    if source:
        conditions.append("r.source = ?")
        params.append(source)

    where = " AND ".join(conditions) if conditions else "1"
    sql = f"SELECT COUNT(DISTINCT r.id) FROM records r WHERE {where}"
    return db.execute(sql, params).fetchone()[0]


def get_record(db: sqlite3.Connection, record_id: str) -> Optional[Dict[str, Any]]:
    row = db.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return None
    rec = dict(row)

    rec["categories"] = [
        r["category"]
        for r in db.execute("SELECT category FROM record_categories WHERE record_id = ?", (record_id,)).fetchall()
    ]
    rec["headings"] = [
        dict(r)
        for r in db.execute("SELECT level, text FROM record_headings WHERE record_id = ? ORDER BY level", (record_id,)).fetchall()
    ]
    rec["outlinks"] = [
        r["url"]
        for r in db.execute("SELECT url FROM record_outlinks WHERE record_id = ?", (record_id,)).fetchall()
    ]

    # Related: same categories
    cats = rec["categories"]
    if cats:
        placeholders = ",".join("?" for _ in cats)
        rec["related"] = [
            dict(r)
            for r in db.execute(
                f"""SELECT r.id, r.title, r.authority_tier, r.source, r.url
                    FROM records r
                    JOIN record_categories rc ON r.id = rc.record_id
                    WHERE rc.category IN ({placeholders}) AND r.id != ?
                    GROUP BY r.id LIMIT 10""",
                [*cats, record_id],
            ).fetchall()
        ]
    else:
        rec["related"] = []

    return rec


def get_topics() -> Dict[str, Dict[str, Any]]:
    return {
        "smart-gates": {"label": "Smart Gates", "categories": ["smart-gates"]},
        "package-versioning": {"label": "Package Versioning", "categories": ["package-versioning"]},
        "identity": {"label": "Identity", "categories": ["identity"]},
        "dapp-discovery": {"label": "dApp Discovery", "categories": ["discovery", "dapp-kit"]},
        "tooling": {"label": "Tooling", "categories": ["tooling"]},
        "game-files": {"label": "Game Files", "categories": ["config", "localization", "world_static_data", "data"]},
    }


def get_topic_records(db: sqlite3.Connection, topic_key: str) -> Dict[str, List[Dict[str, Any]]]:
    topics = get_topics()
    if topic_key not in topics:
        return {}
    cats = topics[topic_key]["categories"]
    placeholders = ",".join("?" for _ in cats)

    rows = db.execute(
        f"""SELECT r.*, GROUP_CONCAT(DISTINCT rc.category) as categories
            FROM records r
            JOIN record_categories rc ON r.id = rc.record_id
            WHERE rc.category IN ({placeholders})
            GROUP BY r.id
            ORDER BY
                CASE r.authority_tier
                    WHEN 'authoritative_source' THEN 1
                    WHEN 'official_docs' THEN 2
                    WHEN 'official_tooling' THEN 3
                    WHEN 'installed_client_observation' THEN 4
                    WHEN 'community_reference' THEN 5
                    ELSE 6
                END""",
        cats,
    ).fetchall()

    by_tier: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        rec = dict(row)
        tier = rec.get("authority_tier", "unofficial")
        by_tier.setdefault(tier, []).append(rec)

    return by_tier


def corpus_summary(db: sqlite3.Connection) -> Dict[str, Any]:
    total = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    by_authority = {}
    for row in db.execute("SELECT authority_tier, COUNT(*) FROM records GROUP BY authority_tier ORDER BY COUNT(*) DESC").fetchall():
        by_authority[row[0]] = row[1]

    by_source = {}
    for row in db.execute("SELECT source, COUNT(*) FROM records GROUP BY source ORDER BY COUNT(*) DESC").fetchall():
        by_source[row[0]] = row[1]

    last_snapshot = db.execute("SELECT created_at FROM snapshots ORDER BY snapshot_id DESC LIMIT 1").fetchone()

    return {
        "total_records": total,
        "by_authority": by_authority,
        "by_source": by_source,
        "last_build": last_snapshot[0] if last_snapshot else "",
    }


AUTHORITY_COLORS = {
    "authoritative_source": "#FFB800",
    "official_docs": "#4CAF50",
    "official_tooling": "#2196F3",
    "installed_client_observation": "#FF9800",
    "community_reference": "#9C27B0",
    "unofficial": "#9E9E9E",
}
