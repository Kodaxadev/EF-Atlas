from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Any, Dict, Iterable


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def url_id(url: str) -> str:
    return sha256_hex(url.encode("utf-8"))


def slug_id(source: str, path: str) -> str:
    cleaned = path.strip("/")
    if cleaned.endswith(".md"):
        cleaned = cleaned[: -len(".md")]
    cleaned = cleaned.replace("/", ":")
    return f"{source}:{cleaned}" if cleaned else f"{source}:"


def authority_flags(authority_tier: str) -> Dict[str, bool]:
    tiers = {
        "authoritative_source",
        "official_docs",
        "official_api_docs",
        "official_tooling",
        "external_foundation_docs",
        "community_reference",
        "legacy_reference",
        "unofficial",
    }
    if authority_tier not in tiers:
        authority_tier = "unofficial"
    return {k: (k == authority_tier) for k in tiers}


def count_by(items: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        v = str(it.get(key, ""))
        out[v] = out.get(v, 0) + 1
    return out

