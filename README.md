# EVE Frontier Builder Knowledge Corpus

A local, reproducible **single source of builder truth** assembled from official EVE Frontier documentation, the whitepaper, and selected public repositories.

This project is intentionally **not tied to any downstream application**. It produces a neutral corpus you can search, index, or analyze later.

## What this is for

- Create a **local JSONL knowledge corpus** from distributed sources (docs, whitepaper, repos).
- Preserve **raw content** plus **content hashes** for integrity checks and change detection.
- Label each record with an **authority tier**, so future agents can separate “official truth” from references.
- Generate **neutral synthesis markdown** that functions as an index (links + labels), not guidance.

## Authority tiers

Each record has:
- `authority_tier`: one of:
  - `authoritative_source`
  - `official_docs`
  - `official_tooling`
  - `community_reference`
  - `unofficial`
- `authority`: a boolean map for convenience (exactly one `true`).

## Data sources

### Layer 1 (official pages)
Fetched **only canonical `.md` URLs** from:
- `https://docs.evefrontier.com/sitemap.md` (excluding `/archive/`)
- `https://whitepaper.evefrontier.com/sitemap.md`

Safety rules enforced:
- Never request any URL with a query string (`?…`).
- Never request `?ask=` or `?q=`.
- Exclude `/archive/`.
- Polite delays and retries.

### Layer 2 (repos)
Cloned and ingested selected repos as **raw file records**:
- `evefrontier/world-contracts`
- `evefrontier/builder-documentation`
- `evefrontier/builder-scaffold`
- `evefrontier/evevault`

Repos are stored under `sources/repos/...` for repeatable re-runs.

## Run commands

### Layer 1 only (docs + whitepaper)

```bash
python ef_scrape.py
```

### Full build (Layer 1 + Layer 2 repos + synthesis)

```bash
python ef_build_corpus.py
```

### Validate outputs

```bash
python ef_validate_corpus.py
```

## Outputs

Build scripts write to `out/`:

- `out/evefrontier_corpus.jsonl`
  - One JSON object per line.
  - Includes: `id`, `slug_id`, `authority_tier`, `content_sha256`, plus raw content fields.
- `out/manifest.json`
  - Run metadata and counts (by source + authority), plus proof that blocked query URLs were not requested.
- `out/failures.json`
  - Machine-readable failures list (empty list on clean runs).
- `out/synthesis/*.md`
  - Neutral index documents derived from the corpus.

## What the synthesis files are (and are not)

They are:
- **Neutral**: lists of sources grouped by authority tier and topic category.
- **Traceable**: each entry points to an underlying `url` (https or `repo://...`).

They are not:
- Recommendations, designs, or downstream architectural conclusions.
- A replacement for reading official sources.

## Re-running safely

- Re-running `python ef_build_corpus.py` overwrites `out/*` files.
- Layer 2 uses shallow clones. If a repo directory exists but is incomplete, the builder will remove it and re-clone.
- Always run `python ef_validate_corpus.py` after building to confirm constraints.

