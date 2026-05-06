from __future__ import annotations

import urllib.parse
from typing import Optional

from .config import BLOCKED_QUERY_SUBSTRINGS


def normalize_url(raw_url: str, base_url: str) -> Optional[str]:
    raw_url = raw_url.strip()
    if not raw_url:
        return None
    if raw_url.startswith("#"):
        return None

    joined = urllib.parse.urljoin(base_url, raw_url)
    parsed = urllib.parse.urlsplit(joined)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def is_blocked_query_url(url: str) -> bool:
    if any(s in url for s in BLOCKED_QUERY_SUBSTRINGS):
        return True
    return "?" in url


def is_canonical_md_url(url: str) -> bool:
    return url.startswith("https://") and url.endswith(".md")


def is_archive_url(url: str) -> bool:
    return "/archive/" in url

