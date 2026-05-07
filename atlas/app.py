"""EF Builder Knowledge Atlas — FastAPI application."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from . import db

app = FastAPI(title="EF Builder Knowledge Atlas")

BASE_DIR = Path(__file__).resolve().parent
env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=False, cache_size=0)
templates = Jinja2Templates(env=env)


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
    limit: int = Query(50),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source, limit=limit)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source)
    d.close()
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "q": q,
            "authority": authority,
            "category": category,
            "source": source,
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
    limit: int = Query(50),
    offset: int = Query(0),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source, limit=limit, offset=offset)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source)
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

Authority order:
1. authoritative_source
2. official_docs
3. official_tooling
4. installed_client_observation
5. community_reference
6. unofficial

Rules:
- Treat indexes as navigation, not conclusions.
- Inspect records before making claims.
- Cite record URLs and hashes.
- Do not treat community references as authoritative.
- Do not make downstream project recommendations unless given project context.

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
    limit: int = Query(20),
):
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source, limit=limit)
    total = db.count_search(d, query=q, authority=authority, category=category, source=source)
    d.close()
    return {"query": q, "total": total, "results": results}


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
async def api_export_jsonl(q: str = Query(""), authority: str = Query(""), category: str = Query(""), source: str = Query("")):
    from fastapi.responses import StreamingResponse
    d = db.get_db()
    results = db.search(d, query=q, authority=authority, category=category, source=source, limit=10000)
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
    }
