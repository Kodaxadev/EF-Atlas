#!/usr/bin/env python3
"""
Validation for EVE Frontier Builder Knowledge Corpus outputs.

Checks:
- JSONL parses
- manifest parses
- required fields exist per record
- no docs/whitepaper record contains query strings or /archive/
- manifest includes counts by source and authority
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


OUT_DIR = Path("out")
CORPUS_PATH = OUT_DIR / "evefrontier_corpus.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"


REQUIRED_FIELDS = {
    "id",
    "source",
    "url",
    "content_sha256",
    "authority_tier",
}


def die(msg: str) -> int:
    print(f"VALIDATION_FAILED: {msg}")
    return 2


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Tuple[int, List[Dict[str, Any]]]:
    records: List[Dict[str, Any]] = []
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            records.append(json.loads(line))
    return n, records


def main() -> int:
    if not CORPUS_PATH.exists():
        return die(f"missing {CORPUS_PATH}")
    if not MANIFEST_PATH.exists():
        return die(f"missing {MANIFEST_PATH}")

    try:
        manifest = load_json(MANIFEST_PATH)
    except Exception as e:  # noqa: BLE001
        return die(f"manifest is not valid JSON: {e!r}")

    try:
        n, records = iter_jsonl(CORPUS_PATH)
    except Exception as e:  # noqa: BLE001
        return die(f"corpus is not valid JSONL: {e!r}")

    if n == 0:
        return die("corpus JSONL has zero records")

    missing_counts = []
    if not isinstance(manifest, dict):
        return die("manifest is not an object")
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        return die("manifest.counts missing or not an object")
    if "by_source" not in counts:
        missing_counts.append("counts.by_source")
    if "by_authority_tier" not in counts:
        missing_counts.append("counts.by_authority_tier")
    if missing_counts:
        return die(f"manifest missing counts: {missing_counts}")

    # Per-record checks
    bad_required = 0
    bad_url = 0
    bad_archive = 0

    for r in records:
        if not isinstance(r, dict):
            bad_required += 1
            continue
        missing = [k for k in REQUIRED_FIELDS if k not in r or r.get(k) in (None, "")]
        if missing:
            bad_required += 1
            continue

        source = str(r.get("source", ""))
        url = str(r.get("url", ""))
        if source in {"docs", "whitepaper"}:
            if "?" in url:
                bad_url += 1
            if "/archive/" in url:
                bad_archive += 1

    if bad_required:
        return die(f"{bad_required} records missing required fields {sorted(REQUIRED_FIELDS)}")
    if bad_url:
        return die(f"{bad_url} docs/whitepaper records contain query strings")
    if bad_archive:
        return die(f"{bad_archive} docs/whitepaper records contain /archive/ URLs")

    print("VALIDATION_OK")
    print(f"records: {n}")
    print(f"counts.by_source: {counts.get('by_source')}")
    print(f"counts.by_authority_tier: {counts.get('by_authority_tier')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

