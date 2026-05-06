from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Tuple

from .config import LAYER1_SOURCES
from .http import fetch_bytes
from .markdown import (
    extract_headings,
    extract_outlinks,
    extract_title,
    parse_frontmatter,
    strip_markdown,
)
from .records import authority_flags, sha256_hex, slug_id, url_id, utc_now_iso
from .sitemap import parse_sitemap_md
from .urls import is_archive_url, is_blocked_query_url


def infer_layer1_category(source: str, path: str) -> str:
    p = path.strip("/")

    if source == "docs":
        if p.startswith("dapps/"):
            return "dapps"
        if p.startswith("tools/"):
            return "tools"
        if p.startswith("smart-assemblies/"):
            return "smart-assemblies"
        if p.startswith("smart-contracts/"):
            if "world" in p:
                return "world"
            return "smart-contracts"
        if p.startswith("eve-vault/"):
            return "wallet"
        return "unknown"

    if source == "whitepaper":
        if p == "technology.md" or p.startswith("technology/"):
            return "technology"
        if p == "game.md" or p.startswith("game/"):
            return "game"
        if p == "economy.md" or p.startswith("economy/"):
            return "economy"
        if "governance" in p:
            return "governance"
        return "unknown"

    return "unknown"


def scrape_layer1(
    *,
    timeout_s: float,
    polite_delay_s: float,
    max_retries: int,
    base_delay_s: float,
    user_agent: str,
    requested_urls: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (records, layer1_manifest_fragment).
    """
    inventories: Dict[str, List[str]] = {}
    blocked_query_urls_seen: List[str] = []
    archive_exclusions_total = 0
    noncanonical_exclusions_total = 0

    sitemap_counts: Dict[str, int] = {}
    sitemap_total_links: Dict[str, int] = {}

    for spec in LAYER1_SOURCES:
        if is_blocked_query_url(spec.sitemap_url):
            raise ValueError(f"sitemap_url contains a query string: {spec.sitemap_url}")

        requested_urls.append(spec.sitemap_url)
        body = fetch_bytes(
            spec.sitemap_url,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay_s=base_delay_s,
            polite_delay_s=polite_delay_s,
        )
        md = body.decode("utf-8", errors="replace")
        urls, blocked_seen, archive_exclusions, noncanonical_exclusions = parse_sitemap_md(
            md, sitemap_url=spec.sitemap_url
        )
        inventories[spec.source] = urls
        sitemap_counts[spec.source] = len(urls)
        sitemap_total_links[spec.source] = len(urls) + archive_exclusions + noncanonical_exclusions + len(
            blocked_seen
        )
        blocked_query_urls_seen.extend(blocked_seen)
        archive_exclusions_total += archive_exclusions
        noncanonical_exclusions_total += noncanonical_exclusions

    seen_url: set[str] = set()
    targets: List[Tuple[str, str, str, str]] = []  # (source, authority_tier, sitemap_url, url)
    for spec in LAYER1_SOURCES:
        for u in inventories.get(spec.source, []):
            if u in seen_url:
                continue
            seen_url.add(u)
            targets.append((spec.source, spec.authority_tier, spec.sitemap_url, u))

    records: List[Dict[str, Any]] = []
    per_host_counts: Dict[str, int] = {}

    for source, authority_tier, sitemap_url, url in targets:
        if is_blocked_query_url(url):
            raise ValueError(f"Blocked query URL discovered in targets: {url}")
        if is_archive_url(url):
            raise ValueError(f"Archive URL discovered in targets: {url}")

        requested_urls.append(url)
        body = fetch_bytes(
            url,
            timeout_s=timeout_s,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay_s=base_delay_s,
            polite_delay_s=polite_delay_s,
        )
        raw_markdown = body.decode("utf-8", errors="replace")
        content_hash = sha256_hex(raw_markdown.encode("utf-8"))

        parsed = urllib.parse.urlsplit(url)
        path = parsed.path
        host = parsed.netloc
        per_host_counts[host] = per_host_counts.get(host, 0) + 1

        frontmatter, md_no_fm = parse_frontmatter(raw_markdown)
        title = extract_title(md_no_fm)
        headings = extract_headings(md_no_fm)
        outlinks = extract_outlinks(raw_markdown, page_url=url)
        category = infer_layer1_category(source, path)
        text = strip_markdown(md_no_fm)

        rec = {
            "id": url_id(url),
            "slug_id": slug_id(source, path),
            "source": source,
            "source_sitemap": sitemap_url,
            "authority_tier": authority_tier,
            "authority": authority_flags(authority_tier),
            "url": url,
            "path": path,
            "retrieved_at": utc_now_iso(),
            "title": title,
            "category": category,
            "source_categories": [category, "whitepaper"] if source == "whitepaper" else [category],
            "frontmatter": frontmatter,
            "headings": headings,
            "outlinks": outlinks,
            "content_sha256": content_hash,
            "raw_markdown": raw_markdown,
            "text": text,
        }

        # Hard acceptance constraints.
        if "/archive/" in rec["url"] or "?" in rec["url"]:
            raise ValueError(f"Invalid URL emitted: {rec['url']}")

        records.append(rec)

    fragment = {
        "layer": "layer1_docs_whitepaper",
        "sitemap_counts": sitemap_counts,
        "sitemap_total_links_observed": sitemap_total_links,
        "archive_exclusions": archive_exclusions_total,
        "noncanonical_exclusions": noncanonical_exclusions_total,
        "blocked_query_urls_seen": sorted(set(blocked_query_urls_seen)),
        "per_host_counts": per_host_counts,
        "records": len(records),
    }
    return records, fragment

