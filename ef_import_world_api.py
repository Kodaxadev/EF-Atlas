#!/usr/bin/env python3
"""
Ingest EVE Frontier World API OpenAPI specs into the Atlas.

Creates one API overview record and one record per endpoint/method
for Stillness (live/mainnet) and Utopia (sandbox/testnet).

Usage:
  python ef_import_world_api.py
  python ef_import_world_api.py --stillness-only
  python ef_import_world_api.py --utopia-only
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("site.db")

ENVIRONMENTS = {
    "stillness": {
        "openapi_url": "https://world-api-stillness.live.tech.evefrontier.com/docs/doc.json",
        "base_url": "https://world-api-stillness.live.tech.evefrontier.com",
        "source": "stillness_world_api",
        "environment": "stillness",
        "chain_environment": "mainnet",
        "source_status": "current_live",
        "production_relevance": "primary",
        "env_categories": ["live", "mainnet", "cycle-5"],
    },
    "utopia": {
        "openapi_url": "https://world-api-utopia.uat.pub.evefrontier.com/docs/doc.json",
        "base_url": "https://world-api-utopia.uat.pub.evefrontier.com",
        "source": "utopia_world_api",
        "environment": "utopia",
        "chain_environment": "testnet",
        "source_status": "active_builder_sandbox",
        "production_relevance": "sandbox_only",
        "env_categories": ["sandbox", "testnet", "builder-testing", "hackathon"],
    },
}

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}

COMMON_CATEGORIES = ["world-api", "rest", "openapi"]


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_openapi(url: str) -> Optional[Dict[str, Any]]:
    """Fetch OpenAPI spec from URL. Uses stdlib only."""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None


def infer_group_category(path: str) -> str:
    """Derive a category tag from the API path."""
    parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
    if not parts:
        return "meta"
    group = parts[0] if not parts[0].startswith("v") else parts[1] if len(parts) > 1 else parts[0]
    return group.replace("-", "_").lower()


def build_endpoint_text(method: str, path: str, op: Dict[str, Any]) -> str:
    """Build searchable text for an endpoint record."""
    lines = []
    summary = op.get("summary", "")
    description = op.get("description", "")
    if summary:
        lines.append(f"Summary: {summary}")
    if description:
        lines.append(f"Description: {description}")

    # Parameters
    params = op.get("parameters", [])
    if params:
        lines.append("Parameters:")
        for p in params:
            loc = p.get("in", "")
            name = p.get("name", "")
            desc = p.get("description", "")
            required = "required" if p.get("required") else "optional"
            lines.append(f"  - [{loc}] {name} ({required}): {desc}")

    # Responses
    responses = op.get("responses", {})
    if responses:
        lines.append("Responses:")
        for code in sorted(responses.keys()):
            resp_desc = responses[code].get("description", "")
            lines.append(f"  - {code}: {resp_desc}")

    # Tags
    tags = op.get("tags", [])
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    return "\n".join(lines)


def ingest_environment(env_key: str, db: sqlite3.Connection) -> Dict[str, Any]:
    """Ingest one environment's OpenAPI spec. Returns stats."""
    env = ENVIRONMENTS[env_key]
    print(f"Ingesting {env_key} from {env['openapi_url']}")

    spec = fetch_openapi(env["openapi_url"])
    if spec is None:
        return {"endpoints": 0, "overview": 0, "fallback": True}

    retrieved_at = utc_now_iso()
    spec_json = json.dumps(spec, ensure_ascii=False)
    spec_hash = sha256_hex(spec_json.encode("utf-8"))

    base_categories = COMMON_CATEGORIES + env["env_categories"]
    source = env["source"]
    permission_status = "official_ccp_api"
    authority_tier = "official_api_docs"

    created_endpoints = 0
    created_overview = 0

    # --- API overview record ---
    overview_id = sha256_hex(f"{env_key}_world_api_overview".encode("utf-8"))
    info = spec.get("info", {})
    overview_text = (
        f"API: {info.get('title', 'World API')}\n"
        f"Version: {info.get('version', '')}\n"
        f"Description: {info.get('description', '')}\n"
        f"Base URL: {env['base_url']}\n"
        f"OpenAPI URL: {env['openapi_url']}\n"
        f"Total paths: {len(spec.get('paths', {}))}"
    )

    _upsert_record(db, {
        "id": overview_id,
        "source": source,
        "authority_tier": authority_tier,
        "permission_status": permission_status,
        "environment": env["environment"],
        "chain_environment": env["chain_environment"],
        "source_status": env["source_status"],
        "production_relevance": env["production_relevance"],
        "url": env["openapi_url"],
        "path": "/docs",
        "title": f"{info.get('title', 'World API')} {info.get('version', '')} Overview",
        "content_sha256": spec_hash,
        "retrieved_at": retrieved_at,
        "text": overview_text,
        "raw_text": spec_json[:50000],
        "categories": base_categories + ["overview"],
        "source_repo": env["base_url"],
        "source_commit": "",
        "source_ref": info.get("version", ""),
        "file_extension": "json",
        "size_bytes": len(spec_json.encode()),
    })
    created_overview = 1

    # --- Endpoint records ---
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, op in methods.items():
            if method.lower() not in HTTP_METHODS:
                continue

            method_upper = method.upper()
            endpoint_id = sha256_hex(f"{env_key}:{method_upper}:{path}".encode("utf-8"))
            title = f"{method_upper} {path}"
            endpoint_url = urllib.parse.urljoin(env["base_url"] + "/", path.lstrip("/"))
            text = build_endpoint_text(method_upper, path, op)
            group = infer_group_category(path)

            _upsert_record(db, {
                "id": endpoint_id,
                "source": source,
                "authority_tier": authority_tier,
                "permission_status": permission_status,
                "environment": env["environment"],
                "chain_environment": env["chain_environment"],
                "source_status": env["source_status"],
                "production_relevance": env["production_relevance"],
                "url": endpoint_url,
                "path": path,
                "title": title,
                "content_sha256": sha256_hex(text.encode()),
                "retrieved_at": retrieved_at,
                "text": text,
                "raw_text": "",
                "categories": base_categories + [group],
                "source_repo": env["base_url"],
                "source_commit": "",
                "source_ref": info.get("version", ""),
                "file_extension": "json",
                "size_bytes": len(text.encode()),
            })
            created_endpoints += 1

    print(f"  Created {created_endpoints} endpoint records + {created_overview} overview")
    return {"endpoints": created_endpoints, "overview": created_overview, "fallback": False}


def _upsert_record(db: sqlite3.Connection, rec: Dict[str, Any]) -> None:
    """Delete old record and insert new one with all fields."""
    rid = rec["id"]
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
            "",
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
            rec.get("source_status", "current"),
            rec.get("production_relevance", "reference"),
        ),
    )

    for cat in rec.get("categories", []):
        db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))


def rebuild_fts(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO records_fts(records_fts) VALUES ('rebuild')")
    db.commit()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Ingest World API OpenAPI specs into Atlas.")
    p.add_argument("--stillness-only", action="store_true", help="Only ingest Stillness API")
    p.add_argument("--utopia-only", action="store_true", help="Only ingest Utopia API")
    args = p.parse_args()

    if not DB_PATH.exists():
        print("site.db not found. Run ef_import_site_db.py first.")
        return 1

    envs_to_run = []
    if args.stillness_only:
        envs_to_run = ["stillness"]
    elif args.utopia_only:
        envs_to_run = ["utopia"]
    else:
        envs_to_run = ["stillness", "utopia"]

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    total_endpoints = 0
    total_overviews = 0
    any_fallback = False

    for env_key in envs_to_run:
        result = ingest_environment(env_key, db)
        total_endpoints += result["endpoints"]
        total_overviews += result["overview"]
        if result["fallback"]:
            any_fallback = True

    db.commit()
    rebuild_fts(db)

    # Stats
    row = db.execute("SELECT COUNT(*) FROM records").fetchone()
    print(f"\nTotal records in DB: {row[0]}")
    row = db.execute(
        "SELECT source, authority_tier, environment, COUNT(*) FROM records "
        "WHERE source LIKE '%world_api%' GROUP BY source, authority_tier, environment"
    ).fetchall()
    for src, tier, env, cnt in row:
        print(f"  {src:25s} | {tier:20s} | {env:10s} | {cnt}")

    if any_fallback:
        print("\nWARNING: Some environments fell back to full-spec ingestion.")

    print(f"\nIngested {total_overviews} overview + {total_endpoints} endpoint records")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
