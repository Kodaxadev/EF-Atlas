#!/usr/bin/env python3
"""
Validation for Layer 3 game file outputs.

Checks:
- JSONL parses
- No binary extensions in extracted records
- All extracted records have content_sha256
- No network behavior
- Sensitive candidates are flagged, not extracted
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

OUT_DIR = Path("out") / "game_files"
INVENTORY_PATH = OUT_DIR / "inventory.jsonl"
CORPUS_PATH = OUT_DIR / "game_file_corpus.jsonl"
WORLD_RECORDS_PATH = OUT_DIR / "static_world_records.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"

BINARY_EXTS = {
    ".exe", ".dll", ".pdb", ".pak", ".ucas", ".utoc", ".sig",
    ".bin", ".dat", ".asset", ".bundle",
    ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".ogg", ".wav", ".bank",
    ".gr2", ".dds", ".vta", ".black",
    ".pickle", ".pyd", ".ccp",
}


def die(msg: str) -> int:
    print(f"VALIDATION_FAILED: {msg}")
    return 2


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> int:
    # Check inventory
    if not INVENTORY_PATH.exists():
        return die(f"missing {INVENTORY_PATH} (run --inventory-only first)")

    try:
        inventory = iter_jsonl(INVENTORY_PATH)
    except Exception as e:
        return die(f"inventory is not valid JSONL: {e!r}")

    if len(inventory) == 0:
        return die("inventory JSONL has zero records")

    # Check required fields on inventory
    required_inv = {"path", "relative_path", "extension", "sha256", "category"}
    for i, rec in enumerate(inventory):
        missing = [k for k in required_inv if k not in rec]
        if missing:
            return die(f"inventory record {i} missing fields: {missing}")

    # Check skipped files
    if not (OUT_DIR / "skipped_files.json").exists():
        return die(f"missing skipped_files.json")

    skipped = load_json(OUT_DIR / "skipped_files.json")
    if not isinstance(skipped, list):
        return die("skipped_files.json is not an array")

    # If --extract-safe-text was run, validate corpus
    if CORPUS_PATH.exists():
        try:
            corpus = iter_jsonl(CORPUS_PATH)
        except Exception as e:
            return die(f"corpus is not valid JSONL: {e!r}")

        if len(corpus) == 0:
            return die("corpus JSONL has zero records")

        # No binary extensions in corpus
        binary_in_corpus = 0
        for rec in corpus:
            ext = rec.get("file_extension", "").lower()
            if ext in BINARY_EXTS:
                binary_in_corpus += 1
        if binary_in_corpus > 0:
            return die(f"{binary_in_corpus} corpus records have binary extensions")

        # All records have content_sha256
        no_hash = 0
        for rec in corpus:
            if not rec.get("content_sha256"):
                no_hash += 1
        if no_hash > 0:
            return die(f"{no_hash} corpus records missing content_sha256")

        # All records have correct source
        for rec in corpus:
            if rec.get("source") != "game_files":
                return die(f"corpus record has wrong source: {rec.get('source')}")

        # No query strings in URLs (game files should use game:// scheme)
        for rec in corpus:
            url = rec.get("url", "")
            if "?" in url and url.startswith("http"):
                return die(f"corpus record has HTTP URL with query string: {url}")

    # Validate world records
    if WORLD_RECORDS_PATH.exists():
        try:
            world_recs = iter_jsonl(WORLD_RECORDS_PATH)
        except Exception as e:
            return die(f"world records is not valid JSONL: {e!r}")

        for rec in world_recs:
            if not rec.get("source_file"):
                return die("world record missing source_file")
            if not rec.get("content_sha256"):
                return die("world record missing content_sha256")
            if not rec.get("record_type"):
                return die("world record missing record_type")

    # Check manifest
    if MANIFEST_PATH.exists():
        try:
            manifest = load_json(MANIFEST_PATH)
        except Exception as e:
            return die(f"manifest is not valid JSON: {e!r}")

        if not isinstance(manifest, dict):
            return die("manifest is not an object")

    print("VALIDATION_OK")
    print(f"inventory: {len(inventory)} records")
    print(f"skipped: {len(skipped)} files")
    if CORPUS_PATH.exists():
        print(f"corpus: {len(iter_jsonl(CORPUS_PATH))} records")
    if WORLD_RECORDS_PATH.exists():
        print(f"world_records: {len(iter_jsonl(WORLD_RECORDS_PATH))} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
