#!/usr/bin/env python3
"""
ef_search.py - simple local search CLI for the EVE Frontier corpus

Usage:
  python ef_search.py "query words here" [--limit 20] [--authority authoritative_source]
                     [--source docs|whitepaper|repo] [--category smart-gates] [--json]

Hard constraints respected: read-only, no scraping, graceful on missing file.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from hashlib import sha256


DEFAULT_CORPUS = os.path.join("out", "evefrontier_corpus.jsonl")


def load_corpus(path):
    if not os.path.exists(path):
        return None, f"Corpus file not found: {path}"
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                records.append(json.loads(ln))
            except Exception:
                # skip malformed lines
                continue
    return records, None


def tokenize(text):
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def score_record(rec, keywords):
    # Weights
    weights = {
        "title": 6,
        "headings": 4,
        "path": 3,
        "url": 2,
        "text": 1,
        "raw_markdown": 1,
    }

    score = 0.0
    counts = Counter()

    # helper to count keyword matches in a field
    def count_in(field):
        val = rec.get(field)
        if val is None:
            return 0
        if isinstance(val, list):
            val = " ".join([str(x) for x in val])
        else:
            val = str(val)
        tokens = tokenize(val)
        c = 0
        for kw in keywords:
            c += tokens.count(kw)
        counts[field] = c
        return c

    for f in weights:
        c = count_in(f)
        score += c * weights[f]

    # Authority boost
    at = rec.get("authority_tier")
    if at is not None:
        try:
            # numeric tiers: smaller is better
            n = int(at)
            score += max(0, 6 - n)
        except Exception:
            s = str(at).lower()
            if any(x in s for x in ("author", "official", "tier1", "primary")):
                score += 4

    # source category boosts
    sc = rec.get("source_categories") or rec.get("categories")
    if isinstance(sc, list):
        if any(sc):
            score += 0.5

    # small boost for having title or url present
    if rec.get("title"):
        score += 0.1
    if rec.get("url"):
        score += 0.05

    return score, counts


def find_snippet(rec, keywords, window=40):
    # Search for keywords in text-like fields and return a short snippet
    fields = ["title", "headings", "text", "raw_markdown", "path", "url"]
    pat = re.compile(r"(" + "|".join(re.escape(k) for k in keywords) + r")", re.I)
    for f in fields:
        val = rec.get(f)
        if val is None:
            continue
        if isinstance(val, list):
            val = " \n ".join([str(x) for x in val])
        s = str(val)
        m = pat.search(s)
        if m:
            start = max(0, m.start() - window)
            end = min(len(s), m.end() + window)
            snippet = s[start:end].replace("\n", " ")
            # highlight by surrounding match with ** (plain text friendly)
            snippet = pat.sub(lambda mm: f"**{mm.group(1)}**", snippet)
            return snippet
    return ""


def matches_filters(rec, args):
    if args.authority:
        at = rec.get("authority_tier")
        if at is None or str(at).lower() != args.authority.lower():
            return False
    if args.source:
        src = rec.get("source")
        if src is None or str(src).lower() != args.source.lower():
            return False
    if args.category:
        cats = rec.get("source_categories") or rec.get("categories") or []
        if isinstance(cats, str):
            cats = [cats]
        if not any(args.category.lower() == str(c).lower() for c in cats):
            return False
    return True


def search(records, query, limit=20, args=None):
    keywords = [w.lower() for w in re.findall(r"\w+", query)]
    if not keywords:
        return []

    scored = []
    for rec in records:
        if args and not matches_filters(rec, args):
            continue
        sc, counts = score_record(rec, keywords)
        if sc <= 0:
            continue
        snippet = find_snippet(rec, keywords)
        scored.append((sc, rec, counts, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for rank, (sc, rec, counts, snippet) in enumerate(scored[:limit], start=1):
        out = {
            "rank": rank,
            "score": sc,
            "title": rec.get("title") or "",
            "url": rec.get("url") or "",
            "source": rec.get("source") or "",
            "authority_tier": rec.get("authority_tier"),
            "source_categories": rec.get("source_categories") or rec.get("categories") or [],
            "matched_snippet": snippet,
            "content_sha256": rec.get("content_sha256") or rec.get("sha256") or compute_sha(rec),
        }
        results.append(out)
    return results


def compute_sha(rec):
    # fallback: hash title+url+text
    s = "".join(str(rec.get(k, "")) for k in ("title", "url", "text", "raw_markdown"))
    return sha256(s.encode("utf-8")).hexdigest()


def main():
    p = argparse.ArgumentParser(description="Search the EVE Frontier corpus (local JSONL).")
    p.add_argument("query", help="Query words in quotes")
    p.add_argument("--corpus", default=DEFAULT_CORPUS, help="Path to corpus JSONL")
    p.add_argument("--limit", type=int, default=20, help="Max number of results to show")
    p.add_argument("--authority", help="Filter by authority_tier value")
    p.add_argument("--source", help="Filter by source (docs|whitepaper|repo)")
    p.add_argument("--category", help="Filter by source category")
    p.add_argument("--json", action="store_true", help="Emit results as JSON")
    args = p.parse_args()

    records, err = load_corpus(args.corpus)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    results = search(records, args.query, limit=args.limit, args=args)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # pretty text output
    for r in results:
        print(f"{r['rank']}. {r['title']}")
        print(f"   url: {r['url']}")
        print(f"   source: {r['source']}  authority_tier: {r.get('authority_tier')}")
        scats = r.get('source_categories') or []
        if scats:
            print(f"   categories: {', '.join(scats)}")
        snippet = r.get('matched_snippet')
        if snippet:
            print(f"   snippet: {snippet}")
        print(f"   content_sha256: {r.get('content_sha256')}")
        print()


if __name__ == "__main__":
    main()
