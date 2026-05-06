from __future__ import annotations

import re
import urllib.parse
from typing import Any, Dict, List, Tuple

from .config import ALLOWED_CORPUS_HOSTS
from .urls import is_archive_url, is_blocked_query_url, is_canonical_md_url, normalize_url


_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def extract_md_links(markdown: str) -> List[str]:
    return [m.group(1).strip() for m in _MD_LINK_RE.finditer(markdown)]


def parse_frontmatter(markdown: str) -> Tuple[Dict[str, Any], str]:
    """
    Returns (frontmatter_dict, markdown_without_frontmatter).
    Best-effort: parses simple 'key: value' lines; otherwise stores raw.
    """
    if not markdown.startswith("---"):
        return {}, markdown

    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, markdown

    fm_lines = lines[1:end_idx]
    rest = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    fm_text = "\n".join(fm_lines).strip()
    if not fm_text:
        return {}, rest
    # Try to parse full YAML frontmatter if PyYAML is available.
    try:
        import yaml  # type: ignore

        try:
            data = yaml.safe_load(fm_text)
            if isinstance(data, dict):
                return data, rest
            # if YAML parsed but not a dict, fall back to simple parsing below
        except Exception:
            # fall through to simple parsing
            pass
    except Exception:
        # PyYAML not installed; fall back to simple parsing
        pass

    # Simple conservative parser: key: value lines only
    fm: Dict[str, Any] = {}
    raw_fallback: List[str] = []
    for ln in fm_lines:
        if not ln.strip():
            continue
        if ":" not in ln:
            raw_fallback.append(ln)
            continue
        k, v = ln.split(":", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raw_fallback.append(ln)
            continue
        fm[k] = v

    if raw_fallback:
        return {"_raw": fm_text}, rest

    return fm, rest


def extract_title(markdown_no_frontmatter: str) -> str:
    for line in markdown_no_frontmatter.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    for line in markdown_no_frontmatter.splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def extract_headings(markdown_no_frontmatter: str) -> List[Dict[str, Any]]:
    headings: List[Dict[str, Any]] = []
    for line in markdown_no_frontmatter.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        headings.append({"level": len(m.group(1)), "text": m.group(2).strip()})
    return headings


def strip_markdown(md: str) -> str:
    md = re.sub(r"```[\s\S]*?```", "", md)
    md = re.sub(r"`([^`]+)`", r"\1", md)
    md = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", md)
    md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", "", md)
    md = re.sub(r"^\s{0,3}#{1,6}\s+", "", md, flags=re.MULTILINE)
    md = re.sub(r"^\s{0,3}>\s?", "", md, flags=re.MULTILINE)
    md = re.sub(r"^\s*[-*+]\s+", "", md, flags=re.MULTILINE)
    md = re.sub(r"^\s*\d+\.\s+", "", md, flags=re.MULTILINE)
    md = re.sub(r"\r\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def extract_outlinks(markdown: str, *, page_url: str) -> List[str]:
    out: List[str] = []
    for raw in extract_md_links(markdown):
        normalized = normalize_url(raw, page_url)
        if normalized is None:
            continue
        if is_blocked_query_url(normalized):
            continue
        if not is_canonical_md_url(normalized):
            continue
        if is_archive_url(normalized):
            continue
        if urllib.parse.urlsplit(normalized).netloc not in ALLOWED_CORPUS_HOSTS:
            continue
        out.append(normalized)

    seen: set[str] = set()
    deduped: List[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        deduped.append(u)
    return deduped

