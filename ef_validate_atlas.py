#!/usr/bin/env python3
"""
Smoke test for the EF Builder Knowledge Atlas.

Usage:
  python ef_import_site_db.py
  python -m uvicorn atlas.app:app --port 8000
  python ef_validate_atlas.py http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required. Install with: pip install requests")
    sys.exit(1)

DB_PATH = Path("site.db")

ROUTES = [
    ("GET", "/", 200, "Home dashboard"),
    ("GET", "/search?q=gate", 200, "FTS search"),
    ("GET", "/t/smart-gates", 200, "Topic: smart-gates"),
    ("GET", "/t/package-versioning", 200, "Topic: package-versioning"),
    ("GET", "/t/identity", 200, "Topic: identity"),
    ("GET", "/t/dapp-discovery", 200, "Topic: dapp-discovery"),
    ("GET", "/t/tooling", 200, "Topic: tooling"),
    ("GET", "/t/game-files", 200, "Topic: game-files"),
    ("GET", "/ai", 200, "AI ingest page"),
    ("GET", "/llms.txt", 200, "LLM agent instructions"),
    ("GET", "/api/corpus-summary", 200, "JSON corpus summary"),
    ("GET", "/api/search?q=authorize_extension", 200, "JSON search API"),
    ("GET", "/api/exports/jsonl?q=gate", 200, "JSONL export"),
    ("GET", "/api/context-list", 200, "Context list API"),
    ("GET", "/api/context/smart-gates", 200, "Context bundle: smart-gates"),
    ("GET", "/api/context/package-versioning", 200, "Context bundle: package-versioning"),
    ("GET", "/api/context/identity", 200, "Context bundle: identity"),
    ("GET", "/api/context/dapp-discovery", 200, "Context bundle: dapp-discovery"),
]


def check_db() -> list[str]:
    errors = []
    if not DB_PATH.exists():
        errors.append(f"site.db not found at {DB_PATH}")
        return errors

    import sqlite3

    db = sqlite3.connect(str(DB_PATH))
    count = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    if count == 0:
        errors.append("records table is empty")

    fts = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='records_fts'"
    ).fetchone()
    if not fts:
        errors.append("records_fts table not found")

    db.close()
    if not errors:
        print(f"  DB: {count} records, FTS index OK")
    return errors


def check_routes(base: str) -> list[str]:
    errors = []
    for method, path, expected_status, label in ROUTES:
        url = urljoin(base, path)
        try:
            resp = requests.get(url, timeout=5)
        except requests.ConnectionError:
            errors.append(f"  FAIL: {label} ({url}) — connection refused")
            continue
        except requests.Timeout:
            errors.append(f"  FAIL: {label} ({url}) — timeout")
            continue

        if resp.status_code != expected_status:
            errors.append(
                f"  FAIL: {label} ({url}) — expected {expected_status}, got {resp.status_code}"
            )
            continue

        # Validate response content for API routes
        if path.startswith("/api/"):
            if "/jsonl" in path:
                # JSONL: each non-empty line must be valid JSON
                lines = resp.text.strip().split("\n")
                non_empty = [line for line in lines if line.strip()]
                if non_empty and all(_is_json(line) for line in non_empty):
                    pass  # valid JSONL
                elif not non_empty:
                    pass  # empty result set is fine
                else:
                    errors.append(f"  FAIL: {label} — invalid JSONL output")
                    continue
            else:
                if not _is_json(resp.text):
                    errors.append(f"  FAIL: {label} — response is not valid JSON")
                    continue

        print(f"  OK: {label} ({url}) -> {resp.status_code}")

    return errors


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python ef_validate_atlas.py http://127.0.0.1:8000")
        return 1

    base = sys.argv[1].rstrip("/")

    print("=== EF Builder Knowledge Atlas Validation ===\n")

    print("[1] Checking database...")
    db_errors = check_db()
    if db_errors:
        for e in db_errors:
            print(f"  ERROR: {e}")
        print("\nDatabase checks FAILED. Run 'python ef_import_site_db.py' first.\n")
        return 1

    print("\n[2] Checking routes...")
    route_errors = check_routes(base)

    print()
    if route_errors:
        for e in route_errors:
            print(e)
        print(f"\n{len(route_errors)} route check(s) FAILED.\n")
        return 1

    print("All checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
