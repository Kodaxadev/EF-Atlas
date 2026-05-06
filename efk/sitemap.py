from __future__ import annotations

from typing import List, Tuple

from .markdown import extract_md_links
from .urls import is_archive_url, is_blocked_query_url, is_canonical_md_url, normalize_url


def parse_sitemap_md(markdown: str, *, sitemap_url: str) -> Tuple[List[str], List[str], int, int]:
    """
    Returns:
      - canonical_md_urls (filtered)
      - blocked_query_urls_seen (from sitemap contents)
      - archive_exclusions_count
      - noncanonical_exclusions_count
    """
    discovered: List[str] = []
    blocked_query_urls_seen: List[str] = []
    archive_exclusions = 0
    noncanonical_exclusions = 0

    for raw in extract_md_links(markdown):
        normalized = normalize_url(raw, sitemap_url)
        if normalized is None:
            continue

        if is_blocked_query_url(normalized):
            blocked_query_urls_seen.append(normalized)
            continue

        if not is_canonical_md_url(normalized):
            noncanonical_exclusions += 1
            continue

        if is_archive_url(normalized):
            archive_exclusions += 1
            continue

        discovered.append(normalized)

    seen: set[str] = set()
    canonical: List[str] = []
    for u in discovered:
        if u in seen:
            continue
        seen.add(u)
        canonical.append(u)

    return canonical, blocked_query_urls_seen, archive_exclusions, noncanonical_exclusions

