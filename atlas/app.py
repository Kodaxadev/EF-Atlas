"""EF Builder Knowledge Atlas — FastAPI application."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from . import db

app = FastAPI(title="EF Builder Knowledge Atlas")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    d = db.get_db()
    summary = db.corpus_summary(d)
    d.close()
    return templates.TemplateResponse("home.html", {"request": request, "authority_colors": db.AUTHORITY_COLORS, **summary})


@app.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = Query(""),
    authority: str = Query(""),
    category: str = Query(""),
    source: str = Query(""),
    environment: str = Query(""),
    chain_environment: str = Query(""),
    source_status: str = Query(""),
    production_relevance: str = Query(""),
    limit: int = Query(50),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source,
                        environment=environment, chain_environment=chain_environment,
                        source_status=source_status, production_relevance=production_relevance,
                        limit=limit)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source,
                            environment=environment, chain_environment=chain_environment,
                            source_status=source_status, production_relevance=production_relevance)
    d.close()
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "q": q,
            "authority": authority,
            "category": category,
            "source": source,
            "environment": environment,
            "chain_environment": chain_environment,
            "source_status": source_status,
            "production_relevance": production_relevance,
            "results": results,
            "total": total,
            "limit": limit,
            "authority_colors": db.AUTHORITY_COLORS,
        },
    )


@app.get("/search/partial", response_class=HTMLResponse)
async def search_partial(
    request: Request,
    q: str = Query(""),
    authority: str = Query(""),
    category: str = Query(""),
    source: str = Query(""),
    environment: str = Query(""),
    chain_environment: str = Query(""),
    source_status: str = Query(""),
    production_relevance: str = Query(""),
    limit: int = Query(50),
    offset: int = Query(0),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source,
                        environment=environment, chain_environment=chain_environment,
                        source_status=source_status, production_relevance=production_relevance,
                        limit=limit, offset=offset)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source,
                            environment=environment, chain_environment=chain_environment,
                            source_status=source_status, production_relevance=production_relevance)
    d.close()
    return templates.TemplateResponse(
        "search_results_partial.html",
        {
            "request": request,
            "results": results,
            "total": total,
            "q": q,
            "authority": authority,
            "category": category,
            "source": source,
            "environment": environment,
            "chain_environment": chain_environment,
            "source_status": source_status,
            "production_relevance": production_relevance,
            "authority_colors": db.AUTHORITY_COLORS,
        },
    )


@app.get("/t/{topic_key}", response_class=HTMLResponse)
async def topic_page(request: Request, topic_key: str):
    topics = db.get_topics()
    if topic_key not in topics:
        return HTMLResponse(f"Topic not found: {topic_key}", status_code=404)

    topic = topics[topic_key]
    d = db.get_db()
    by_tier = db.get_topic_records(d, topic_key)
    d.close()
    return templates.TemplateResponse(
        "topic.html",
        {"request": request, "topic_key": topic_key, "topic": topic, "by_tier": by_tier, "authority_colors": db.AUTHORITY_COLORS},
    )


@app.get("/r/{record_id:path}", response_class=HTMLResponse)
async def record_page(request: Request, record_id: str):
    d = db.get_db()
    rec = db.get_record(d, record_id)
    d.close()
    if not rec:
        return HTMLResponse(f"Record not found: {record_id}", status_code=404)
    return templates.TemplateResponse(
        "record.html",
        {"request": request, "rec": rec, "authority_colors": db.AUTHORITY_COLORS},
    )


@app.get("/diff", response_class=HTMLResponse)
async def diff_page(request: Request):
    diff_path = Path("out") / "diff" / "changed_records.json"
    diff_data = None
    if diff_path.exists():
        diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
    return templates.TemplateResponse("diff.html", {"request": request, "diff": diff_data, "authority_colors": db.AUTHORITY_COLORS})


@app.get("/ai", response_class=HTMLResponse)
async def ai_page(request: Request):
    return templates.TemplateResponse("ai.html", {"request": request})


@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    return """# EVE Frontier Builder Knowledge Corpus

Start here:
- /api/corpus-summary
- /api/topics/smart-gates
- /api/topics/package-versioning
- /api/topics/identity
- /api/topics/dapp-discovery
- /api/topics/tooling
- /api/topics/game-files
- /api/topics/community-references
- /api/topics/game-data
- /api/topics/world-api

Authority order:
1. authoritative_source
2. official_docs
3. official_api_docs
4. official_tooling
5. external_foundation_docs
6. installed_client_observation
7. community_reference
8. legacy_reference
9. unofficial

Rules:
- Treat indexes as navigation, not conclusions.
- Inspect records before making claims.
- Cite record URLs and hashes.
- Do not treat community references as authoritative.
- Do not make downstream project recommendations unless given project context.
- Stillness is the current live player shard, but it is still testnet. Use Stillness for current gameplay and player-facing behavior.
- Utopia is the dev/mod/hackathon sandbox server. Use Utopia for builder testing, hackathon flows, and experimental development.
- Do not call Stillness mainnet unless an official source confirms that changed.
- Do not use Utopia evidence as current Stillness player-shard truth unless explicitly comparing environments.
- Legacy reference sources (Project Awakening, MUD) are from the EVM-era architecture. Do not use them for current Sui/Move implementation decisions unless the task is explicitly a historical comparison.
- External foundation docs (Sui, Walrus/Seal) provide foundational platform knowledge. They are not EVE Frontier-specific truth.
- EVE Datacore is a community game/static data explorer. Use it for browsing static game data and item lookups. Do not use it as evidence for contract logic, official package IDs, or API behavior.
- Do not use docs.evefrontier.com ?ask= or ?q= endpoints as a backend data source.
- For World API records, use /api/context/world-api or /api/topics/world-api, or filter by category=world-api, source=stillness_world_api, source=utopia_world_api, environment=stillness, or environment=utopia. Do not rely on text search for the term "world-api" because categories are stored separately from full-text content in the FTS index.

Default task scope:
- Default mode is current_builder
- Current means Sui Move, not Solidity
- Sui objects/events, not MUD tables
- Stillness for live production/mainnet
- Utopia for active builder sandbox (testnet)
- EVE Vault / dapp-kit for wallet/session
- World API/OpenAPI for REST evidence
- Legacy/EVM/MUD only for historical comparison when explicitly requested
- Community references are hints/discovery, not implementation truth

Dapp ideation claim discipline:
- Separate every claim into: Confirmed by Atlas, Inferred from Atlas, Assumption, Unknown/needs verification
- Do not say "buildable today," "production-ready," "deployed," "auto-enforced," or "available" unless supported by inspected Atlas records
- For enforcement claims, specify evidence type: objective on-chain evidence, World API evidence, indexed event evidence, manual attestation, oracle input, or speculative future integration
- Community/reference records can inspire ideas but cannot prove implementation feasibility
- Before making any technical feasibility claim, inspect the relevant /api/records/{id} source and include the record ID, title, authority_tier, record_api_url, and snippet

When producing evidence tables, every row must include:
title, URL, authority_tier, record ID, record_api_url, direct snippet.

Do not include records that were not fetched through /api/records/{id}.
Do not use placeholder phrases such as "surfaced in search" or "representative record."
"""


# --- API endpoints ---

@app.get("/api/corpus-summary", response_class=JSONResponse)
async def api_corpus_summary():
    d = db.get_db()
    summary = db.corpus_summary(d)
    d.close()
    return summary


@app.get("/api/search", response_class=JSONResponse)
async def api_search(
    q: str = Query(""),
    authority: str = Query(""),
    category: str = Query(""),
    source: str = Query(""),
    environment: str = Query(""),
    chain_environment: str = Query(""),
    source_status: str = Query(""),
    production_relevance: str = Query(""),
    mode: str = Query("current_builder"),
    limit: int = Query(20),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source,
                        environment=environment, chain_environment=chain_environment,
                        source_status=source_status, production_relevance=production_relevance,
                        limit=limit)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source,
                            environment=environment, chain_environment=chain_environment,
                            source_status=source_status, production_relevance=production_relevance)
    d.close()
    return {
        "query": q,
        "total": total,
        "results": results,
        "mode": mode,
        "mode_advisory": "Mode is advisory in this version. Use authority, source, category, and environment filters for precise retrieval.",
    }


@app.get("/api/records/{record_id:path}", response_class=JSONResponse)
async def api_record(record_id: str):
    d = db.get_db()
    rec = db.get_record(d, record_id)
    d.close()
    if not rec:
        return JSONResponse({"error": "not found"}, status_code=404)
    return rec


@app.get("/api/topics/{topic_key}", response_class=JSONResponse)
async def api_topic(topic_key: str):
    topics = db.get_topics()
    if topic_key not in topics:
        return JSONResponse({"error": "topic not found"}, status_code=404)
    d = db.get_db()
    by_tier = db.get_topic_records(d, topic_key)
    d.close()
    return {"topic": topics[topic_key], "records_by_authority": by_tier}


@app.get("/api/exports/jsonl")
async def api_export_jsonl(
    q: str = Query(""),
    authority: str = Query(""),
    category: str = Query(""),
    source: str = Query(""),
    environment: str = Query(""),
    chain_environment: str = Query(""),
    source_status: str = Query(""),
    production_relevance: str = Query(""),
):
    from fastapi.responses import StreamingResponse
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source,
                        environment=environment, chain_environment=chain_environment,
                        source_status=source_status, production_relevance=production_relevance,
                        limit=10000)
    d.close()

    def stream():
        for rec in results:
            yield json.dumps(rec, ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-jsonl")


@app.get("/api/context/{topic_key}", response_class=JSONResponse)
async def api_context_bundle(topic_key: str):
    d = db.get_db()
    bundle = db.get_context_bundle(d, topic_key)
    d.close()
    if not bundle:
        return JSONResponse({"error": "topic not found"}, status_code=404)
    return bundle


@app.get("/api/context-list", response_class=JSONResponse)
async def api_context_list():
    topics = db.get_topics()
    return {
        "topics": [
            {"key": k, "label": v["label"], "context_url": f"/api/context/{k}"}
            for k, v in topics.items()
        ],
        "rules": db.CONTEXT_RULES,
        "authority_order": db.AUTHORITY_ORDER,
        "agent_policy": db.AGENT_POLICY,
    }


@app.get("/api/agent-policy", response_class=JSONResponse)
async def api_agent_policy():
    return db.AGENT_POLICY
