# EF Builder Knowledge Atlas

A searchable, authority-tiered knowledge base for EVE Frontier builders — corpus, web atlas, and API.

[![Live](https://img.shields.io/badge/live-atlas.kodaxa.dev-blue)](https://atlas.kodaxa.dev)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue)](https://www.python.org/)
[![Deployed on Render](https://img.shields.io/badge/deployed%20on-render-black)](https://render.com/)

## Quickstart

Get the full stack running locally in 5 commands:

```bash
pip install -r requirements.txt
python ef_scrape.py              # Layer 1: official docs + whitepaper
python ef_build_corpus.py        # Layer 2: repos → JSONL corpus
python ef_import_site_db.py      # Import corpus → SQLite with FTS5
python main.py                   # Start web atlas at http://localhost:3000
```

Then visit `http://localhost:3000` to search, browse topics, and explore records.

## AI-Ready

Point any LLM or agent at [`atlas.kodaxa.dev/llms.txt`](https://atlas.kodaxa.dev/llms.txt) for structured instructions on how to query the atlas, interpret authority tiers, and cite records with hashes. For programmatic access, use `/api/context/{topic}` to get compact, agent-consumable context bundles with top records, search suggestions, and export links.

## Overview

EF Builder Knowledge Atlas ingests official documentation, whitepapers, repositories, and community sources into a unified, searchable database. Every record is labeled with an **authority tier**, so you and AI agents can distinguish official truth from community references.

The project has two parts:

1. **Corpus builder** — Python scripts that scrape, clone, and assemble a local JSONL knowledge corpus from distributed sources.
2. **Web atlas** — a FastAPI application ([atlas.kodaxa.dev](https://atlas.kodaxa.dev)) that loads the corpus into SQLite with full-text search, provides a web UI for browsing and searching, and exposes a JSON API for programmatic access and AI context bundles.

## Web Atlas

Visit [atlas.kodaxa.dev](https://atlas.kodaxa.dev) to:

- **Search** the full corpus with filters (authority tier, category, source)
- **Browse topics** like Smart Gates, Identity, dApp Discovery, Tooling, and Game Data
- **Inspect individual records** with full metadata, headings, outlinks, and related entries
- **Export** search results as JSONL for offline use
- **Feed AI agents** via `/llms.txt` and `/api/context/{topic}` endpoints

## API Reference

The atlas exposes a JSON API under `/api/` and a few special-purpose endpoints.

### Search

```
GET /api/search?q=<query>&authority=<tier>&category=<cat>&source=<src>&limit=<n>
```

| Param | Default | Description |
|---|---|---|
| `q` | `""` | Full-text search query (FTS5) |
| `authority` | `""` | Filter by authority tier |
| `category` | `""` | Filter by category tag |
| `source` | `""` | Filter by source name |
| `limit` | `20` | Max results |

**Response:**
```json
{
  "query": "smart gates",
  "total": 42,
  "results": [
    {
      "id": "official-docs/smart-gates/intro",
      "title": "Smart Gates Overview",
      "authority_tier": "official_docs",
      "source": "docs.evefrontier.com",
      "url": "https://docs.evefrontier.com/...",
      "text": "...",
      "categories": "smart-gates",
      "snippet": "..."
    }
  ]
}
```

### Record

```
GET /api/records/{record_id}
```

Returns a single record with categories, headings, outlinks, and related records. 404 if not found.

### Topics

```
GET /api/topics/{topic_key}
```

Returns topic metadata and records grouped by authority tier. Available topics:

| Key | Label |
|---|---|
| `smart-gates` | Smart Gates |
| `package-versioning` | Package Versioning |
| `identity` | Identity |
| `dapp-discovery` | dApp Discovery |
| `tooling` | Tooling |
| `game-files` | Game Files |
| `community-references` | Community References |
| `game-data` | Game Data |

### Corpus Summary

```
GET /api/corpus-summary
```

Returns total record count, breakdown by authority tier and source, and last build timestamp.

### AI Context Bundle

```
GET /api/context/{topic_key}
GET /api/context-list
```

Returns a compact, agent-consumable bundle: top records per authority tier, search suggestions, export URL, and usage rules. `/api/context-list` returns all available topics.

### Export

```
GET /api/exports/jsonl?q=<query>&authority=<tier>&category=<cat>&source=<src>
```

Streams matching records as newline-delimited JSON (max 10,000).

### AI Instructions

```
GET /llms.txt
```

Returns plain-text instructions for LLMs on how to use the atlas, authority rules, and required citation format.

## Authority Tiers

Each record is assigned one authority tier. Higher tiers take precedence when resolving conflicting information.

| Tier | Color | Description |
|---|---|---|
| `authoritative_source` | Gold | Direct source-of-truth content |
| `official_docs` | Green | Official EVE Frontier documentation |
| `official_tooling` | Blue | Official repositories and tooling |
| `installed_client_observation` | Orange | Observations from the installed client |
| `community_reference` | Purple | Community-maintained references |
| `unofficial` | Gray | Unofficial or third-party content |

**Rules:**
- Treat indexes as navigation, not conclusions.
- Inspect records before making claims.
- Prefer `authoritative_source` over tooling or community references.
- Cite record URLs and `content_sha256` hashes when referencing facts.
- Do not treat community references as authoritative.

## Building the Corpus

The corpus builder assembles raw content from official and community sources into a local JSONL file.

### Layer 1 — Official Docs

Scrapes canonical `.md` URLs from:
- `https://docs.evefrontier.com/sitemap.md`
- `https://whitepaper.evefrontier.com/sitemap.md`

Safety rules: no query strings, no `/archive/`, polite delays and retries.

```bash
python ef_scrape.py
```

### Layer 2 — Repos + Full Build

Clones and ingests selected repos as raw file records:
- `evefrontier/world-contracts`
- `evefrontier/builder-documentation`
- `evefrontier/builder-scaffold`
- `evefrontier/evevault`

```bash
python ef_build_corpus.py
```

### Validate

```bash
python ef_validate_corpus.py
```

### Outputs (`out/`)

| File | Description |
|---|---|
| `evefrontier_corpus.jsonl` | One JSON object per line with `id`, `slug_id`, `authority_tier`, `content_sha256`, and raw content |
| `manifest.json` | Run metadata, counts by source + authority |
| `failures.json` | Machine-readable failures list (empty on clean runs) |
| `synthesis/*.md` | Neutral index documents grouped by authority and topic |

## Layer 3 — Additional Data Sources

These scripts import community and game-file data into the SQLite atlas database.

### Import to SQLite (with FTS5)

```bash
python ef_import_site_db.py                        # default corpus
python ef_import_site_db.py --corpus out/evefrontier_corpus.jsonl
python ef_import_site_db.py --game-files out/game_files/game_file_corpus.jsonl
python ef_import_site_db.py --all                  # import both
```

Creates `site.db` with FTS5 full-text search index, categories, headings, outlinks, and build snapshots.

### Scetrov Community Notes

Imports the Scetrov Frontier knowledge matrix CSV into `site.db` as `community_reference` tier.

```bash
# Place CSV at ~/Downloads/frontier-site-knowledge-matrix.csv first
python ef_import_scetrov_notes.py
```

### EVE Datacore

Registers EVE Datacore (`evedataco.re`) as a community reference entry for game data, item lookups, and world references.

```bash
python ef_import_eve_datacore.py
```

## Running the Web Atlas

### Local

```bash
pip install -r requirements.txt
python main.py
# or: uvicorn atlas.app:app --host 0.0.0.0 --port 3000
```

Requires `site.db` in the project root (built via `ef_import_site_db.py`).

### Render Deployment

Deployed via Procfile:

```
web: python main.py
```

Set `PORT` environment variable as needed (default: 3000). Ensure `site.db` is present or provisioned as a persistent disk.

## Dependencies

```
fastapi
uvicorn
jinja2
starlette>=0.40.0,<0.50.0
```

> [!WARNING]
> **Re-running safely:**
> - `ef_build_corpus.py` overwrites all `out/*` files.
> - Layer 2 uses shallow clones — if a repo directory exists but is incomplete, it will be removed and re-cloned.
> - `ef_import_site_db.py` **deletes and rebuilds `site.db` from scratch**. Running it again will erase the existing database.
> - Always run `ef_validate_corpus.py` after building to confirm constraints.
