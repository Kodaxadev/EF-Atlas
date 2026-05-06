#!/usr/bin/env python3
"""
Layer 1 entrypoint for the EVE Frontier Builder Knowledge Corpus.

Scrapes official docs + whitepaper from sitemap.md into:
- out/evefrontier_corpus.jsonl
- out/manifest.json
- out/failures.json

For the multi-source build (docs + whitepaper + repos + synthesis), run:
  python ef_build_corpus.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from efk.layer1_docs import scrape_layer1
from efk.records import count_by, utc_now_iso
from efk.urls import is_blocked_query_url


OUT_DIR = Path("out")
CORPUS_PATH = OUT_DIR / "evefrontier_corpus.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"
FAILURES_PATH = OUT_DIR / "failures.json"


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_no_blocked_requests(requested_urls: List[str]) -> None:
    bad = [u for u in requested_urls if is_blocked_query_url(u)]
    if bad:
        raise RuntimeError(f"Blocked query URLs were requested: {bad[:5]}{'...' if len(bad) > 5 else ''}")


def main() -> int:
    started_at = utc_now_iso()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    requested_urls: List[str] = []

    timeout_s = 30.0
    polite_delay_s = 0.5
    max_retries = 4
    base_delay_s = 0.75
    user_agent = "EVEFrontierDocsScraper/2.0 (+https://docs.evefrontier.com/)"

    records, layer1_manifest = scrape_layer1(
        timeout_s=timeout_s,
        polite_delay_s=polite_delay_s,
        max_retries=max_retries,
        base_delay_s=base_delay_s,
        user_agent=user_agent,
        requested_urls=requested_urls,
    )

    with CORPUS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    ensure_no_blocked_requests(requested_urls)

    ended_at = utc_now_iso()
    failures: List[Dict[str, Any]] = []

    manifest: Dict[str, Any] = {
        "started_at": started_at,
        "ended_at": ended_at,
        "records_written": len(records),
        "failures": len(failures),
        "requested_urls_count": len(requested_urls),
        "requested_urls_sample": requested_urls[:50],
        "proof_no_ask_or_q_requested": {
            "checked_at": utc_now_iso(),
            "any_contains_ask": any("?ask=" in u for u in requested_urls),
            "any_contains_q": any("?q=" in u for u in requested_urls),
            "any_contains_query_string": any("?" in u for u in requested_urls),
        },
        "counts": {
            "by_source": count_by(records, "source"),
            "by_authority_tier": count_by(records, "authority_tier"),
        },
        "layers": [layer1_manifest],
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(FAILURES_PATH, failures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

