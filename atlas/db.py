"""Database helpers for the EF Knowledge Atlas site."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Resolve DB_PATH relative to this module's location (works in any cwd, including Railway)
DB_PATH = Path(__file__).resolve().parent.parent / "site.db"


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
    environment: str = "",
    chain_environment: str = "",
    source_status: str = "",
    production_relevance: str = "",
) -> List[Dict[str, Any]]:
    conditions = []
    params: list = []

    has_query = query.strip() != ""
    if has_query:
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
    if environment:
        conditions.append("r.environment = ?")
        params.append(environment)
    if chain_environment:
        conditions.append("r.chain_environment = ?")
        params.append(chain_environment)
    if source_status:
        conditions.append("r.source_status = ?")
        params.append(source_status)
    if production_relevance:
        conditions.append("r.production_relevance = ?")
        params.append(production_relevance)

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
                WHEN 'official_api_docs' THEN 3
                WHEN 'official_tooling' THEN 4
                WHEN 'external_foundation_docs' THEN 5
                WHEN 'installed_client_observation' THEN 6
                WHEN 'community_reference' THEN 7
                WHEN 'legacy_reference' THEN 8
                ELSE 9
            END,
            r.title
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = db.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]

    # Generate simple snippets from text for query results
    if has_query and results:
        keywords = query.strip().lower().split()
        for rec in results:
            text = rec.get("text", "") or ""
            snippet = _extract_snippet(text, keywords)
            rec["snippet"] = snippet

    return results


def _extract_snippet(text: str, keywords: list, window: int = 60) -> str:
    if not text or not keywords:
        return ""
    low = text.lower()
    for kw in keywords:
        idx = low.find(kw)
        if idx >= 0:
            start = max(0, idx - window)
            end = min(len(text), idx + len(kw) + window)
            snippet = text[start:end].replace("\n", " ")
            # Highlight keyword
            pat = re.compile(re.escape(kw), re.I)
            snippet = pat.sub(f"**{kw}**", snippet)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text) else ""
            return f"{prefix}{snippet}{suffix}"
    return ""


def count_search(
    db: sqlite3.Connection,
    query: str = "",
    authority: str = "",
    category: str = "",
    source: str = "",
    environment: str = "",
    chain_environment: str = "",
    source_status: str = "",
    production_relevance: str = "",
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
    if environment:
        conditions.append("r.environment = ?")
        params.append(environment)
    if chain_environment:
        conditions.append("r.chain_environment = ?")
        params.append(chain_environment)
    if source_status:
        conditions.append("r.source_status = ?")
        params.append(source_status)
    if production_relevance:
        conditions.append("r.production_relevance = ?")
        params.append(production_relevance)

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
        "community-references": {
            "label": "Community References",
            "categories": [
                "develop", "devsecops", "debugging", "getting-started", "links", "references",
                "community-references", "tooling", "world-api", "static-data",
                "smart-gates", "move-security",
            ],
        },
        "game-data": {"label": "Game Data", "categories": ["static-data", "game-data", "items", "world-data"]},
        "world-api": {"label": "World API", "categories": ["world-api", "rest", "openapi"]},
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
                    WHEN 'official_api_docs' THEN 3
                    WHEN 'official_tooling' THEN 4
                    WHEN 'external_foundation_docs' THEN 5
                    WHEN 'installed_client_observation' THEN 6
                    WHEN 'community_reference' THEN 7
                    WHEN 'legacy_reference' THEN 8
                    ELSE 9
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

    by_authority = []
    for row in db.execute("SELECT authority_tier, COUNT(*) FROM records GROUP BY authority_tier ORDER BY COUNT(*) DESC").fetchall():
        by_authority.append((row[0], row[1]))

    by_source = []
    for row in db.execute("SELECT source, COUNT(*) FROM records GROUP BY source ORDER BY COUNT(*) DESC").fetchall():
        by_source.append((row[0], row[1]))

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
    "official_api_docs": "#00BCD4",
    "official_tooling": "#2196F3",
    "external_foundation_docs": "#8BC34A",
    "installed_client_observation": "#FF9800",
    "community_reference": "#9C27B0",
    "legacy_reference": "#795548",
    "unofficial": "#9E9E9E",
}

AUTHORITY_COLORS_TUPLE = tuple(AUTHORITY_COLORS.items())

AUTHORITY_ORDER = [
    "authoritative_source",
    "official_docs",
    "official_api_docs",
    "official_tooling",
    "external_foundation_docs",
    "installed_client_observation",
    "community_reference",
    "legacy_reference",
    "unofficial",
]

CONTEXT_RULES = [
    "Indexes are navigation, not conclusions.",
    "Inspect records before making claims.",
    "Prefer authoritative_source over tooling or community references.",
    "Cite record URLs and content_sha256 hashes when referencing facts.",
    "Do not treat community references as authoritative.",
    "Do not make downstream project recommendations unless given project context.",
    "Community reference sources (Scetrov notes, EVE Datacore) are not sufficient for contract logic, official package IDs, or registry schema claims.",
    "Stillness is the current live player shard, but it is still testnet. Use Stillness for current gameplay and player-facing behavior.",
    "Utopia is the dev/mod/hackathon sandbox server. Use Utopia for builder testing, hackathon flows, and experimental development.",
    "Do not call Stillness mainnet unless an official source confirms that changed.",
    "Do not use Utopia evidence as current Stillness player-shard truth unless explicitly comparing environments.",
    "Legacy reference sources (Project Awakening, MUD) are from the EVM-era architecture. Do not use them for current Sui/Move implementation decisions unless the task is explicitly a historical comparison.",
    "External foundation docs (Sui, Walrus/Seal) provide foundational platform knowledge for Move, GraphQL, storage, and access control. They are not EVE Frontier-specific truth.",
    "EVE Datacore is a community game/static data explorer. Use it for browsing static game data and item lookups. Do not use it as evidence for contract logic, official package IDs, or API behavior.",
    "Do not use docs.evefrontier.com ?ask= or ?q= endpoints as a backend data source.",
]

AGENT_POLICY = {
    "default_mode": "current_builder",
    "current_builder_scope": "Sui Move, Stillness (current live shard, testnet), Utopia (dev/mod/hackathon sandbox, testnet), EVE Vault/dapp-kit, World API/OpenAPI",
    "forbidden_default_assumptions": [
        "Do not assume Solidity/EVM architecture for current Frontier work",
        "Do not assume MUD tables/entities for current Frontier work",
        "Do not assume Ethereum wallet/session patterns",
    ],
    "claim_confidence_rule": (
        "When proposing dApps, separate every claim into: "
        "Confirmed by Atlas (backed by inspected /api/records/{id}), "
        "Inferred from Atlas (logical extension of Atlas records), "
        "Assumption (unstated prerequisite), "
        "Unknown/needs verification (cannot be proven from current corpus). "
        "Do not say 'buildable today,' 'production-ready,' 'deployed,' 'auto-enforced,' "
        "or 'available' unless supported by specific inspected Atlas records. "
        "Community/reference records can inspire ideas but cannot prove implementation feasibility."
    ),
    "enforcement_claim_rule": (
        "Before claiming something is enforced, automated, or guaranteed, specify the evidence type: "
        "objective on-chain evidence, World API evidence, indexed event evidence, "
        "manual attestation, oracle input, or speculative future integration. "
        "Before making any technical feasibility claim, inspect the relevant "
        "/api/records/{id} source and include the record ID, title, authority_tier, "
        "record_api_url, and snippet."
    ),
    "legacy_rule": "Legacy/EVM/MUD sources are for historical comparison only. Use only when the task explicitly requests historical comparison.",
    "community_rule": "Community references (Scetrov, EVE Datacore) are hints and discovery aids, not implementation truth. Do not base contract logic or official schema claims on them.",
    "dapp_ideation_rule": "When ideating dApps, ground proposals in current Sui Move capabilities, EVE Vault wallet/session patterns, World API endpoints, and official docs. Do not propose EVM-era patterns as current solutions.",
    "environment_rule": "Stillness = current live shard (testnet). Utopia = dev/mod/hackathon sandbox (testnet). Do not use Utopia as evidence for current Stillness player-shard truth unless explicitly comparing environments.",
}


def get_context_bundle(db: sqlite3.Connection, topic_key: str) -> Optional[Dict[str, Any]]:
    """Return a compact agent-consumable context bundle for a topic."""
    topics = get_topics()
    if topic_key not in topics:
        return None

    topic = topics[topic_key]
    cats = topic["categories"]

    # Get top records per authority tier (limit 5 per tier)
    records_by_tier = get_topic_records(db, topic_key)
    top_records = []
    for tier in AUTHORITY_ORDER:
        tier_records = records_by_tier.get(tier, [])
        for rec in tier_records[:5]:
            rid = rec["id"]
            # Verify the record is resolvable via /api/records/{id}
            exists = db.execute("SELECT 1 FROM records WHERE id = ?", (rid,)).fetchone()
            if not exists:
                continue
            top_records.append({
                "id": rid,
                "record_api_url": f"/api/records/{rid}",
                "title": rec.get("title", ""),
                "url": rec.get("url", ""),
                "authority_tier": tier,
                "source": rec.get("source", ""),
                "categories": rec.get("categories", ""),
                "content_sha256": rec.get("content_sha256", ""),
                "path": rec.get("path", ""),
            })

    # Search suggestions: common keywords from category names + headings
    placeholders = ",".join("?" for _ in cats)
    headings_query = f"""
        SELECT DISTINCT rh.text
        FROM record_headings rh
        JOIN record_categories rc ON rh.record_id = rc.record_id
        WHERE rc.category IN ({placeholders})
        LIMIT 10
    """
    headings = [r[0] for r in db.execute(headings_query, cats).fetchall()]

    return {
        "topic": topic_key,
        "label": topic["label"],
        "categories": cats,
        "authority_order": AUTHORITY_ORDER,
        "rules": CONTEXT_RULES,
        "top_records": top_records,
        "search_suggestions": [h for h in headings if h and len(h) > 3],
        "export_url": f"/api/exports/jsonl?category={cats[0]}",
        "default_mode": AGENT_POLICY["default_mode"],
        "scope_guidance": AGENT_POLICY["current_builder_scope"],
        "legacy_usage_rule": AGENT_POLICY["legacy_rule"],
        "community_usage_rule": AGENT_POLICY["community_rule"],
        "environment_rule": AGENT_POLICY["environment_rule"],
        "claim_confidence_rule": AGENT_POLICY["claim_confidence_rule"],
        "enforcement_claim_rule": AGENT_POLICY["enforcement_claim_rule"],
    }
