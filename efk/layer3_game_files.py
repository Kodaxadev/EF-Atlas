"""Layer 3: Game file inventory and safe static-data extraction.

Read-only scan of installed EVE Frontier game client.
Never modifies, unpacks, or bypasses any protections.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .records import count_by, sha256_hex, slug_id, utc_now_iso


AUTHORITY_TIER = "installed_client_observation"
GAME_DIR_ID_PREFIX = "game_file"

BINARY_EXTS = {
    ".exe", ".dll", ".pdb", ".pak", ".ucas", ".utoc", ".sig",
    ".bin", ".dat", ".asset", ".bundle",
    ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".ogg", ".wav", ".bank",
    ".gr2", ".dds", ".vta", ".black",
    ".pickle", ".pyd", ".ccp",
}

SAFE_TEXT_EXTS = {
    ".json", ".jsonc", ".jsonl", ".csv", ".tsv",
    ".xml", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".conf", ".txt", ".md", ".log",
    ".lua", ".proto", ".graphql", ".gql",
}

CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("config", ["config", "settings", "prefs", "options", "start.ini", "carbon.json"]),
    ("localization", ["loc", "lang", "localization", "string_table", "l10n"]),
    ("world_static_data", ["solar", "system", "constellation", "region", "universe", "stargate", "celestial", "fsd"]),
    ("data", ["data", "db", "database", "manifest", "index"]),
    ("log", ["log", "trace", "debug", "crash", "dump"]),
    ("script", ["lua", "py", "script", "macro"]),
    ("schema", ["schema", "proto", "graphql", "gql", "thrift"]),
    ("binary", []),
    ("asset", ["model", "texture", "mesh", "anim", "audio", "sound", "font", "shader"]),
]

SENSITIVE_PATTERNS = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "jwt_token"),
    (re.compile(r"[Bb]earer\s+[A-Za-z0-9_.-]{10,}"), "bearer_token"),
    (re.compile(r"(?:token|secret|key|auth|api[_-]?key|access[_-]?token)\s*[=:]\s*[A-Za-z0-9_.-]{20,}", re.I), "long_hex_token"),
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "email"),
    (re.compile(r"[Ss]ession[_\s]?[Ii]d\s*[=:]\s*\S+"), "session_id"),
    (re.compile(r"[Aa]ccount[_\s]?[Ii]d\s*[=:]\s*\S+"), "account_id"),
    (re.compile(r"[Ww]allet[_\s]?[Aa]ddress\s*[=:]\s*0x[A-Fa-f0-9]{40}"), "wallet_address"),
    (re.compile(r"[Cc]ookie\s*[=:]\s*\S+"), "cookie"),
    (re.compile(r"[Aa][Pp][Ii][_\-]?[Kk]ey\s*[=:]\s*\S+"), "api_key"),
    (re.compile(r"password\s*[=:]\s*\S+", re.I), "password"),
]

WORLD_DATA_LABEL_RE = re.compile(
    r"(?:Solar System|Asteroid Belt|Inner Planet|Ecosystem|Station|Stargate|Gate)\s*:\s*(.+)",
    re.I,
)

COORD_RE = re.compile(
    r"(?:position|pos|x|y|z|radius)\s*[:=]\s*([\-0-9.e+]+)",
    re.I,
)

ID_RE = re.compile(
    r"(?:solar_system_id|belt_id|planet_id|site_id|ecosystem_id|station_id|stargate_id)\s*[:=]\s*([0-9]+)",
    re.I,
)


def classify_file(rel_path: str, ext: str, raw_text: str = "") -> str:
    p = rel_path.replace("\\", "/").lower()
    text = (p + " " + (raw_text or "")).lower()[:2000]

    if ext in BINARY_EXTS:
        return "binary"

    for cat, keywords in CATEGORY_KEYWORDS:
        if cat == "binary":
            continue
        if any(kw in text for kw in keywords):
            return cat

    if ext in {".gr2", ".dds", ".vta", ".black", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".ogg", ".wav", ".bank"}:
        return "asset"

    return "unknown"


def detect_sensitive_keywords(text: str) -> List[str]:
    found = []
    for pat, label in SENSITIVE_PATTERNS:
        if pat.search(text):
            found.append(label)
    return found


def redact_sensitive_text(text: str) -> str:
    result = text
    for pat, label in SENSITIVE_PATTERNS:
        result = pat.sub(f"[REDACTED:{label}]", result)
    return result


def is_safe_text_file(ext: str) -> bool:
    return ext in SAFE_TEXT_EXTS


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def scan_game_files(game_dir: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    game_dir = game_dir.resolve()
    if not game_dir.is_dir():
        raise FileNotFoundError(f"Game directory not found: {game_dir}")

    inventory: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    sensitive: List[Dict[str, Any]] = []

    prune_dirs = {".git", "node_modules", "target", "dist", "build", ".next", "__pycache__"}
    prune_top = {"ResFiles"}

    for root, dirs, files in os.walk(game_dir):
        depth = len(Path(root).relative_to(game_dir).parts)
        if depth == 0:
            dirs[:] = [d for d in dirs if d not in prune_top and d not in prune_dirs]
        else:
            dirs[:] = [d for d in dirs if d not in prune_dirs]

        for fn in files:
            fpath = Path(root) / fn
            ext = fpath.suffix.lower()
            try:
                stat = fpath.stat()
                size = stat.st_size
                # Only fully hash files under 50MB. For larger files, hash header + size.
                if size < 50_000_000:
                    content_hash = sha256_hex(fpath.read_bytes())
                else:
                    with fpath.open("rb") as fh:
                        header = fh.read(65536)
                    content_hash = sha256_hex(header + str(size).encode())
            except Exception:
                continue

            rel = str(fpath.relative_to(game_dir)).replace("\\", "/")
            is_text = is_safe_text_file(ext)
            category = "binary" if ext in BINARY_EXTS else classify_file(rel, ext)

            rec = {
                "path": str(fpath),
                "relative_path": rel,
                "extension": ext,
                "size_bytes": size,
                "sha256": content_hash,
                "is_text_candidate": is_text,
                "category": category,
                "matched_keywords": [],
            }

            # Check for sensitive content in text candidates
            if is_text and size < 5_000_000:
                try:
                    text = safe_read_text(fpath)
                    sens = detect_sensitive_keywords(text)
                    if sens:
                        rec["matched_keywords"] = list(set(sens))
                        sensitive.append({
                            "relative_path": rel,
                            "flags": sens,
                            "action": "flagged_not_extracted",
                        })
                except Exception:
                    pass

            if ext in BINARY_EXTS:
                skipped.append({"relative_path": rel, "extension": ext, "size_bytes": size, "reason": "binary/asset extension"})
            else:
                inventory.append(rec)

    manifest = {
        "layer": "layer3_game_files",
        "game_dir": str(game_dir),
        "total_files_scanned": len(inventory) + len(skipped),
        "inventory_count": len(inventory),
        "skipped_count": len(skipped),
        "sensitive_candidates_count": len(sensitive),
        "by_category": count_by(inventory, "category"),
        "by_extension": _top_exts(inventory, 20),
    }

    return inventory, skipped, sensitive, manifest


def _top_exts(items: List[Dict[str, Any]], n: int) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        ext = str(it.get("extension", ""))
        out[ext] = out.get(ext, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1])[:n])


def strip_jsonc_comments(text: str) -> str:
    result = []
    i = 0
    in_string = False
    while i < len(text):
        c = text[i]
        if in_string:
            result.append(c)
            if c == '\\' and i + 1 < len(text):
                result.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
            result.append(c)
            i += 1
            continue

        if c == '/' and i + 1 < len(text):
            nc = text[i + 1]
            if nc == '/':
                while i < len(text) and text[i] != '\n':
                    i += 1
                continue
            if nc == '*':
                i += 2
                while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                    i += 1
                i += 2
                continue

        result.append(c)
        i += 1

    return "".join(result)


def extract_labels_from_comments(text: str) -> List[str]:
    labels = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            m = WORLD_DATA_LABEL_RE.search(stripped)
            if m:
                labels.append(m.group(1).strip())
    return labels


def derive_world_records(text: str, source_file: str, content_hash: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    labels = extract_labels_from_comments(text)

    ids_found = ID_RE.findall(text)
    coords = COORD_RE.findall(text)

    label_map: Dict[str, str] = {}
    for line in text.splitlines():
        m = WORLD_DATA_LABEL_RE.search(line)
        if m:
            label_map[m.group(0).split(":")[0].strip().lower().replace(" ", "_")] = m.group(1).strip()

    if labels or ids_found:
        rec_type = "solar_system" if any("solar" in l.lower() for l in labels) else "world_data"
        records.append({
            "source": "game_files",
            "authority_tier": AUTHORITY_TIER,
            "record_type": rec_type,
            "source_file": source_file,
            "content_sha256": content_hash,
            "labels": labels,
            "ids_found": [int(x) for x in ids_found[:20]],
            "coordinates": [float(x) for x in coords[:20]],
        })

    return records


def extract_safe_text_files(game_dir: Path, inventory: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    game_dir = game_dir.resolve()
    corpus: List[Dict[str, Any]] = []
    world_records: List[Dict[str, Any]] = []

    prune_dirs = {".git", "node_modules", "target", "dist", "build", ".next", "__pycache__"}
    prune_top = {"ResFiles"}

    for root, dirs, files in os.walk(game_dir):
        depth = len(Path(root).relative_to(game_dir).parts)
        if depth == 0:
            dirs[:] = [d for d in dirs if d not in prune_top and d not in prune_dirs]
        else:
            dirs[:] = [d for d in dirs if d not in prune_dirs]

        for fn in files:
            fpath = Path(root) / fn
            ext = fpath.suffix.lower()
            if not is_safe_text_file(ext):
                continue

            rel = str(fpath.relative_to(game_dir)).replace("\\", "/")
            try:
                stat = fpath.stat()
                size = stat.st_size
                if size > 5_000_000:
                    continue
                raw = safe_read_text(fpath)
                content_hash = sha256_hex(raw.encode("utf-8"))
                category = classify_file(rel, ext, raw)
                sens = detect_sensitive_keywords(raw)
                safe_raw = redact_sensitive_text(raw) if sens else raw
                text_clean = re.sub(r"\s+", " ", safe_raw).strip()[:5000]

                rec = {
                    "id": slug_id(GAME_DIR_ID_PREFIX, rel),
                    "slug_id": f"game:{rel}",
                    "source": "game_files",
                    "authority_tier": AUTHORITY_TIER,
                    "authority": {AUTHORITY_TIER: True},
                    "url": f"game://{rel}",
                    "path": f"/{rel}",
                    "file_extension": ext,
                    "size_bytes": size,
                    "retrieved_at": utc_now_iso(),
                    "title": fn,
                    "category": category,
                    "source_categories": [category],
                    "matched_keywords": list(set(sens)) if sens else [],
                    "content_sha256": content_hash,
                    "raw_markdown": safe_raw,
                    "text": text_clean,
                    "frontmatter": {},
                    "headings": [],
                    "outlinks": [],
                }
                corpus.append(rec)

                if ext in {".json", ".jsonc"}:
                    derived = derive_world_records(raw, rel, content_hash)
                    world_records.extend(derived)

            except Exception:
                continue

    manifest = {
        "layer": "layer3_game_files_text",
        "text_files_extracted": len(corpus),
        "world_records_derived": len(world_records),
        "by_category": count_by(corpus, "category"),
    }

    return corpus, world_records, manifest
