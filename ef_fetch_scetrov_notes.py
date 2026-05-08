#!/usr/bin/env python3
"""
Fetch Scetrov community notes from the live site (frontier.scetrov.live).

Crawls sitemap.xml, fetches each page, extracts title and body content,
and writes sources/scetrov_notes.jsonl.

Usage:
  python ef_fetch_scetrov_notes.py

Safety:
  - Max 200 pages
  - Timeout 15s per page
  - Total budget 600s
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SITEMAP_URL = "https://frontier.scetrov.live/sitemap.xml"
BASE_URL = "https://frontier.scetrov.live"  # Canonical base for source_repo field
JSONL_PATH = Path("sources") / "scetrov_notes.jsonl"

MAX_PAGES = 200
PAGE_TIMEOUT = 15  # seconds
TOTAL_BUDGET = 600  # seconds

FIXED_CATEGORIES = [
    "community-references",
    "devsecops",
    "tooling",
    "world-api",
    "static-data",
    "smart-gates",
    "move-security",
]

# Skip non-content pages (taxonomy and root index only)
def should_skip_url(url: str) -> bool:
    """Check if a URL should be skipped (taxonomy pages, root index)."""
    path = urllib.parse.urlparse(url).path
    # Skip taxonomy listing pages
    if path in ("/categories/", "/tags/", "/categories/index.html", "/tags/index.html"):
        return True
    # Skip root index (just the homepage)
    if path in ("/", "/index.html"):
        return True
    return False


def fetch_url(url: str, timeout: int = PAGE_TIMEOUT) -> bytes | None:
    """Fetch a URL using stdlib urllib."""
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EF-Atlas-Fetcher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()
    except Exception as e:
        print(f"  WARNING: Failed to fetch {url}: {e}")
        return None


def parse_sitemap(xml_bytes: bytes) -> list[str]:
    """Extract URLs from sitemap.xml."""
    try:
        root = ET.fromstring(xml_bytes)
        # Handle namespace
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        urls = []
        for loc in root.iter(f"{ns}loc"):
            if loc.text:
                urls.append(loc.text.strip())
        return urls
    except Exception as e:
        print(f"SCETROV_FETCH_FAILED: sitemap parse error: {e}")
        return []


def extract_page_data(html: str, url: str) -> dict | None:
    """Extract title, body text, headings, and outlinks from a Hugo page."""
    # Title: from <title> tag
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if not title_match:
        return None
    raw_title = title_match.group(1).strip()
    # Strip " :: Unofficial EVE Frontier Development Notes" suffix
    title = raw_title.split(" :: ")[0].strip() if " :: " in raw_title else raw_title
    if not title:
        return None

    # Derive section from URL path
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    path_parts = [p for p in path.strip("/").split("/") if p]
    section = path_parts[0] if path_parts else "home"

    # Extract headings: look for <h1>, <h2>, <h3>
    headings = []
    for m in re.finditer(r"<h([123])[^>]*>(.*?)</h\1>", html, re.DOTALL | re.IGNORECASE):
        level = int(m.group(1))
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if text and text != title:
            headings.append({"level": level, "text": text})

    # Extract body text: get content between <main> or <article> or <div class="content">
    body = ""
    for pattern in [r"<main[^>]*>(.*?)</main>", r"<article[^>]*>(.*?)</article>",
                    r'<div[^>]*class="content"[^>]*>(.*?)</div>']:
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            body = m.group(1)
            break

    if not body:
        # Fallback: extract all <p> tags
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
        body = "\n\n".join(paragraphs)

    # Strip HTML tags from body
    plain_text = re.sub(r"<[^>]+>", "", body).strip()
    # Normalize whitespace
    plain_text = re.sub(r"\n{3,}", "\n\n", plain_text)
    plain_text = re.sub(r"[ \t]+", " ", plain_text)
    plain_text = plain_text.strip()

    if len(plain_text) < 50:
        # Page likely has no useful content
        return None

    # Extract outlinks: <a href="http...">
    outlinks = []
    for m in re.finditer(r'<a[^>]+href=["\']((?:https?:)?//[^"\']+)["\'][^>]*>', html):
        link = m.group(1)
        if link.startswith("//"):
            link = "https:" + link
        # Skip internal links and asset links
        if not any(skip in link for skip in [".css", ".js", ".png", ".svg", ".woff"]):
            outlinks.append(link)

    # Build id from path
    rid = f"scetrov/{path.strip('/').rstrip('/')}"
    if not rid or rid == "scetrov/":
        rid = "scetrov/home"

    return {
        "id": rid,
        "slug_id": "",
        "source": "frontier_scetrov_live",
        "authority_tier": "community_reference",
        "permission_status": "openly_allowed_by_author",
        "url": url,
        "path": path,
        "title": title,
        "content_sha256": hashlib.sha256(title.encode() + plain_text.encode()).hexdigest(),
        "retrieved_at": "",
        "text": plain_text,
        "raw_text": plain_text,
        "source_repo": BASE_URL,
        "source_commit": "",
        "source_ref": "",
        "file_extension": "md",
        "size_bytes": len(plain_text.encode()),
        "source_categories": FIXED_CATEGORIES,
        "section": section,
        "headings": headings,
        "outlinks": outlinks,
    }


def main() -> int:
    start_time = time.time()

    # Fetch sitemap
    print(f"Fetching sitemap from {SITEMAP_URL}...")
    sitemap_bytes = fetch_url(SITEMAP_URL, timeout=PAGE_TIMEOUT)
    if not sitemap_bytes:
        print("SCETROV_FETCH_FAILED: Could not fetch sitemap.xml")
        print("records_imported: 0")
        return 1

    urls = parse_sitemap(sitemap_bytes)
    print(f"Found {len(urls)} URLs in sitemap")

    # Filter: skip non-content pages, keep first 200
    urls = [u for u in urls if not should_skip_url(u)]
    urls = urls[:MAX_PAGES]
    print(f"Will fetch {len(urls)} content pages (max {MAX_PAGES})")

    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

    fetched = 0
    skipped = 0
    records = []

    for i, url in enumerate(urls):
        elapsed = time.time() - start_time
        if elapsed > TOTAL_BUDGET:
            print(f"\n  TIME BUDGET EXCEEDED ({TOTAL_BUDGET}s). Stopping at page {i+1}/{len(urls)}.")
            break

        print(f"  [{i+1}/{len(urls)}] {url}")
        html_bytes = fetch_url(url)
        if not html_bytes:
            skipped += 1
            continue

        html = html_bytes.decode("utf-8", errors="replace")
        page_data = extract_page_data(html, url)
        if not page_data:
            skipped += 1
            continue

        records.append(page_data)
        fetched += 1

    # Write JSONL
    with open(JSONL_PATH, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    elapsed = time.time() - start_time
    print(f"\nFetched {fetched} pages, skipped {skipped}, in {elapsed:.1f}s")
    print(f"Wrote {JSONL_PATH}")

    if fetched == 0:
        print("SCETROV_FETCH_FAILED: No pages were successfully fetched")
        print("records_imported: 0")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
