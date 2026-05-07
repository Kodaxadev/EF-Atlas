#!/usr/bin/env python3
"""
Layer 3: Game file inventory and safe static-data extraction.

Usage:
  python ef_scrape_game_files.py "D:\EVE Frontier" --inventory-only
  python ef_scrape_game_files.py "D:\EVE Frontier" --extract-safe-text

Hard constraints:
  - Read-only. Never modify game files.
  - Never bypass protections, DRM, anti-cheat, encryption, or packed binaries.
  - Never upload anything.
  - Skip binary/assets by default.
  - Redact obvious sensitive strings in logs/text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from efk.layer3_game_files import (
    AUTHORITY_TIER,
    extract_safe_text_files,
    scan_game_files,
)
from efk.records import count_by, utc_now_iso


OUT_DIR = Path("out") / "game_files"
INVENTORY_PATH = OUT_DIR / "inventory.jsonl"
SUMMARY_PATH = OUT_DIR / "inventory_summary.md"
CORPUS_PATH = OUT_DIR / "game_file_corpus.jsonl"
WORLD_RECORDS_PATH = OUT_DIR / "static_world_records.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"
SKIPPED_PATH = OUT_DIR / "skipped_files.json"
SENSITIVE_PATH = OUT_DIR / "private_or_sensitive_candidates.md"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_inventory_summary(inventory, skipped, sensitive, inv_manifest) -> str:
    lines = [
        "# Game File Inventory Summary",
        "",
        f"**Game directory**: `{inv_manifest.get('game_dir', 'unknown')}`",
        "",
        "## Counts",
        f"- Total files scanned: {inv_manifest.get('total_files_scanned', 0)}",
        f"- Inventory records: {inv_manifest.get('inventory_count', 0)}",
        f"- Skipped (binary/asset): {inv_manifest.get('skipped_count', 0)}",
        f"- Sensitive candidates flagged: {inv_manifest.get('sensitive_candidates_count', 0)}",
        "",
        "## By Category",
    ]
    for cat, n in sorted(inv_manifest.get("by_category", {}).items()):
        lines.append(f"- {cat}: {n}")
    lines.append("")
    lines.append("## Top Extensions")
    for ext, n in inv_manifest.get("by_extension", {}).items():
        lines.append(f"- {ext}: {n}")
    lines.append("")
    if sensitive:
        lines.append("## Sensitive Candidates (flagged, not extracted)")
        for s in sensitive[:50]:
            lines.append(f"- `{s['relative_path']}` — flags: {', '.join(s['flags'])}")
        if len(sensitive) > 50:
            lines.append(f"- ... and {len(sensitive) - 50} more")
        lines.append("")
    return "\n".join(lines)


def build_sensitive_md(sensitive) -> str:
    lines = [
        "# Private or Sensitive File Candidates",
        "",
        "These files were flagged for containing patterns that may include",
        "sensitive data. They were **not extracted** into the corpus.",
        "",
    ]
    if not sensitive:
        lines.append("No sensitive candidates found.")
    else:
        lines.append(f"**Total flagged**: {len(sensitive)}")
        lines.append("")
        for s in sensitive:
            lines.append(f"- `{s['relative_path']}` — flags: {', '.join(s['flags'])} — action: {s['action']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Layer 3: Game file inventory and safe text extraction.")
    p.add_argument("game_dir", help="Path to EVE Frontier game directory")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory-only", action="store_true", help="Build inventory only (fast)")
    mode.add_argument("--extract-safe-text", action="store_true", help="Build inventory and extract safe text files")
    args = p.parse_args()

    game_dir = Path(args.game_dir)
    if not game_dir.is_dir():
        print(f"Error: Game directory not found: {game_dir}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started_at = utc_now_iso()

    print(f"Scanning: {game_dir}")
    inventory, skipped, sensitive, inv_manifest = scan_game_files(game_dir)

    # Write inventory
    write_jsonl(INVENTORY_PATH, inventory)
    write_json(SKIPPED_PATH, skipped)
    write_md(SENSITIVE_PATH, build_sensitive_md(sensitive))
    write_md(SUMMARY_PATH, build_inventory_summary(inventory, skipped, sensitive, inv_manifest))

    print(f"Inventory: {len(inventory)} records -> {INVENTORY_PATH}")
    print(f"Skipped: {len(skipped)} files -> {SKIPPED_PATH}")
    print(f"Sensitive: {len(sensitive)} flagged -> {SENSITIVE_PATH}")

    if args.inventory_only:
        return 0

    # Extract safe text
    print("Extracting safe text files...")
    corpus, world_records, text_manifest = extract_safe_text_files(game_dir, inventory)

    write_jsonl(CORPUS_PATH, corpus)
    write_jsonl(WORLD_RECORDS_PATH, world_records)

    ended_at = utc_now_iso()
    manifest = {
        "started_at": started_at,
        "ended_at": ended_at,
        "inventory": inv_manifest,
        "text_extraction": text_manifest,
        "combined_counts": {
            "by_source": {
                "game_files_inventory": len(inventory),
                "game_files_corpus": len(corpus),
                "game_files_world_records": len(world_records),
            },
            "by_category": count_by(corpus, "category"),
            "by_authority_tier": {AUTHORITY_TIER: len(corpus)},
        },
    }
    write_json(MANIFEST_PATH, manifest)

    print(f"Corpus: {len(corpus)} records -> {CORPUS_PATH}")
    print(f"World records: {len(world_records)} -> {WORLD_RECORDS_PATH}")
    print(f"Manifest -> {MANIFEST_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
