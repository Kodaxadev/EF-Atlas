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
    ("GET", "/api/agent-policy", 200, "Agent policy endpoint"),
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


def check_context_bundle_records(base: str) -> list[str]:
    """Verify every record in context bundles resolves via /api/records/{id}."""
    errors = []

    # Get all context bundle URLs
    try:
        resp = requests.get(urljoin(base, "/api/context-list"), timeout=5)
        ctx_list = resp.json()
    except Exception as e:
        errors.append(f"  FAIL: /api/context-list — {e}")
        return errors

    topics = ctx_list.get("topics", [])
    total_checked = 0
    total_ok = 0

    for topic in topics:
        topic_key = topic["key"]
        try:
            resp = requests.get(urljoin(base, f"/api/context/{topic_key}"), timeout=5)
            bundle = resp.json()
        except Exception as e:
            errors.append(f"  FAIL: /api/context/{topic_key} — {e}")
            continue

        records = bundle.get("top_records", [])
        for rec in records:
            rid = rec.get("id", "")
            api_url = rec.get("record_api_url", "")
            total_checked += 1

            # Check record_api_url field exists
            if not api_url:
                errors.append(f"  FAIL: {topic_key}/{rid} — missing record_api_url")
                continue

            # Verify record resolves
            try:
                rec_resp = requests.get(urljoin(base, api_url), timeout=5)
                if rec_resp.status_code == 200:
                    rec_data = rec_resp.json()
                    # Verify IDs match
                    if rec_data.get("id") != rid:
                        errors.append(
                            f"  FAIL: {topic_key}/{rid} — /api/records returned id={rec_data.get('id')}"
                        )
                    else:
                        total_ok += 1
                else:
                    errors.append(
                        f"  FAIL: {topic_key}/{rid} — {api_url} returned {rec_resp.status_code}"
                    )
            except Exception as e:
                errors.append(f"  FAIL: {topic_key}/{rid} — {api_url} — {e}")

    print(f"  Context bundle records: {total_ok}/{total_checked} resolvable")
    return errors


def check_agent_policy(base: str) -> list[str]:
    """Validate agent scope policy, claim discipline, and corpus absence content."""
    errors = []

    # Check /llms.txt contains current_builder, Confirmed by Atlas, and corpus absence text
    try:
        resp = requests.get(urljoin(base, "/llms.txt"), timeout=5)
        if "current_builder" not in resp.text:
            errors.append("  FAIL: /llms.txt does not contain 'current_builder'")
        else:
            print("  OK: /llms.txt contains 'current_builder'")
        if "Confirmed by Atlas" not in resp.text:
            errors.append("  FAIL: /llms.txt does not contain 'Confirmed by Atlas'")
        else:
            print("  OK: /llms.txt contains 'Confirmed by Atlas'")
        if "not represented in the current Atlas corpus" not in resp.text:
            errors.append("  FAIL: /llms.txt does not contain 'not represented in the current Atlas corpus'")
        else:
            print("  OK: /llms.txt contains corpus absence rule text")
    except Exception as e:
        errors.append(f"  FAIL: /llms.txt — {e}")

    # Check /api/agent-policy returns required keys
    required_keys = ["default_mode", "current_builder_scope", "forbidden_default_assumptions",
                     "claim_confidence_rule", "enforcement_claim_rule",
                     "corpus_absence_rule", "external_source_rule", "authority_action_rule",
                     "legacy_rule", "community_rule", "dapp_ideation_rule", "environment_rule"]
    try:
        resp = requests.get(urljoin(base, "/api/agent-policy"), timeout=5)
        policy = resp.json()
        for key in required_keys:
            if key not in policy:
                errors.append(f"  FAIL: /api/agent-policy missing key '{key}'")
        if not errors:
            print(f"  OK: /api/agent-policy has all {len(required_keys)} required keys")
    except Exception as e:
        errors.append(f"  FAIL: /api/agent-policy — {e}")

    # Check context bundles include all rules
    for topic in ["smart-gates", "dapp-discovery"]:
        try:
            resp = requests.get(urljoin(base, f"/api/context/{topic}"), timeout=5)
            bundle = resp.json()
            for key in ["default_mode", "scope_guidance", "claim_confidence_rule",
                        "enforcement_claim_rule", "corpus_absence_rule",
                        "external_source_rule", "authority_action_rule"]:
                if key not in bundle:
                    errors.append(f"  FAIL: /api/context/{topic} missing '{key}'")
            if all(k in bundle for k in ["default_mode", "scope_guidance", "claim_confidence_rule",
                                          "enforcement_claim_rule", "corpus_absence_rule",
                                          "external_source_rule", "authority_action_rule"]):
                print(f"  OK: /api/context/{topic} includes all policy rules")
        except Exception as e:
            errors.append(f"  FAIL: /api/context/{topic} — {e}")

    return errors


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Validate EF Builder Knowledge Atlas.")
    p.add_argument("base_url", help="Base URL, e.g. http://127.0.0.1:8000 or https://atlas.kodaxa.dev")
    p.add_argument("--production", action="store_true", help="Skip local DB check (remote validation only)")
    args = p.parse_args()

    base = args.base_url.rstrip("/")

    print("=== EF Builder Knowledge Atlas Validation ===\n")

    if not args.production:
        print("[1] Checking database...")
        db_errors = check_db()
        if db_errors:
            for e in db_errors:
                print(f"  ERROR: {e}")
            print("\nDatabase checks FAILED. Run 'python ef_import_site_db.py' first.\n")
            return 1
    else:
        print("[1] Skipping local DB check (production mode)")
        db_errors = []

    print("\n[2] Checking routes...")
    route_errors = check_routes(base)

    print("\n[3] Checking context bundle record resolvability...")
    context_errors = check_context_bundle_records(base)

    print("\n[4] Checking agent scope policy content...")
    policy_errors = check_agent_policy(base)

    all_errors = route_errors + context_errors + policy_errors
    print()
    if all_errors:
        for e in all_errors:
            print(e)
        print(f"\n{len(all_errors)} check(s) FAILED.\n")
        return 1

    print("All checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
