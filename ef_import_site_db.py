#!/usr/bin/env python3
"""
Import JSONL corpus into SQLite with FTS5 search index.

Usage:
  python ef_import_site_db.py
  python ef_import_site_db.py --corpus out/evefrontier_corpus.jsonl
  python ef_import_site_db.py --game-files out/game_files/game_file_corpus.jsonl
  python ef_import_site_db.py --all
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path("site.db")
CORPUS_PATH = Path("out") / "evefrontier_corpus.jsonl"
GAME_CORPUS_PATH = Path("out") / "game_files" / "game_file_corpus.jsonl"
MANIFEST_PATH = Path("out") / "manifest.json"


SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    slug_id TEXT,
    source TEXT,
    authority_tier TEXT,
    url TEXT,
    path TEXT,
    title TEXT,
    content_sha256 TEXT,
    retrieved_at TEXT,
    text TEXT,
    raw_text TEXT,
    source_repo TEXT,
    source_commit TEXT,
    source_ref TEXT,
    file_extension TEXT,
    size_bytes INTEGER,
    permission_status TEXT
);

CREATE TABLE IF NOT EXISTS record_categories (
    record_id TEXT,
    category TEXT,
    FOREIGN KEY (record_id) REFERENCES records(id)
);

CREATE TABLE IF NOT EXISTS record_headings (
    record_id TEXT,
    level INTEGER,
    text TEXT,
    FOREIGN KEY (record_id) REFERENCES records(id)
);

CREATE TABLE IF NOT EXISTS record_outlinks (
    record_id TEXT,
    url TEXT,
    FOREIGN KEY (record_id) REFERENCES records(id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    manifest_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    title, text, url, path, source, slug_id,
    content='records',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS records_fts_insert AFTER INSERT ON records
BEGIN
    INSERT INTO records_fts(rowid, title, text, url, path, source, slug_id)
    VALUES (
        NEW.rowid,
        COALESCE(NEW.title, ''),
        COALESCE(NEW.text, ''),
        COALESCE(NEW.url, ''),
        COALESCE(NEW.path, ''),
        COALESCE(NEW.source, ''),
        COALESCE(NEW.slug_id, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS records_fts_delete AFTER DELETE ON records
BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, text, url, path, source, slug_id)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.text, OLD.url, OLD.path, OLD.source, OLD.slug_id);
END;

CREATE TRIGGER IF NOT EXISTS records_fts_update AFTER UPDATE ON records
BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, text, url, path, source, slug_id)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.text, OLD.url, OLD.path, OLD.source, OLD.slug_id);
    INSERT INTO records_fts(rowid, title, text, url, path, source, slug_id)
    VALUES (
        NEW.rowid,
        COALESCE(NEW.title, ''),
        COALESCE(NEW.text, ''),
        COALESCE(NEW.url, ''),
        COALESCE(NEW.path, ''),
        COALESCE(NEW.source, ''),
        COALESCE(NEW.slug_id, '')
    );
END;
"""


def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def init_db(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA)
    db.commit()


def iter_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def insert_records(db: sqlite3.Connection, records: List[Dict[str, Any]]) -> int:
    count = 0
    for rec in records:
        rid = rec.get("id") or rec.get("slug_id")
        if not rid:
            continue

        # Upsert: delete old + insert new
        db.execute("DELETE FROM record_outlinks WHERE record_id = ?", (rid,))
        db.execute("DELETE FROM record_headings WHERE record_id = ?", (rid,))
        db.execute("DELETE FROM record_categories WHERE record_id = ?", (rid,))
        db.execute("DELETE FROM records WHERE id = ?", (rid,))

        db.execute(
            """INSERT INTO records
               (id, slug_id, source, authority_tier, url, path, title,
                content_sha256, retrieved_at, text, raw_text,
                source_repo, source_commit, source_ref, file_extension, size_bytes,
                permission_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rid,
                rec.get("slug_id", ""),
                rec.get("source", ""),
                rec.get("authority_tier", ""),
                rec.get("url", ""),
                rec.get("path", ""),
                rec.get("title", ""),
                rec.get("content_sha256", ""),
                rec.get("retrieved_at", ""),
                rec.get("text", ""),
                rec.get("raw_markdown") or rec.get("raw_text", ""),
                rec.get("source_repo", ""),
                rec.get("source_commit", ""),
                rec.get("source_ref", ""),
                rec.get("file_extension", ""),
                rec.get("size_bytes", 0),
                rec.get("permission_status", ""),
            ),
        )

        # Categories
        cats = rec.get("source_categories") or rec.get("categories") or []
        if isinstance(cats, str):
            cats = [cats]
        for cat in cats:
            db.execute("INSERT INTO record_categories (record_id, category) VALUES (?, ?)", (rid, cat))

        # Headings
        headings = rec.get("headings") or []
        if isinstance(headings, list):
            for h in headings:
                if isinstance(h, dict):
                    db.execute(
                        "INSERT INTO record_headings (record_id, level, text) VALUES (?, ?, ?)",
                        (rid, h.get("level", 0), h.get("text", "")),
                    )

        # Outlinks
        outlinks = rec.get("outlinks") or []
        if isinstance(outlinks, list):
            for u in outlinks:
                db.execute("INSERT INTO record_outlinks (record_id, url) VALUES (?, ?)", (rid, u))

        count += 1

    db.commit()
    return count


def rebuild_fts(db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO records_fts(records_fts) VALUES ('rebuild')")
    db.commit()


def record_snapshot(db: sqlite3.Connection, manifest_path: Path = MANIFEST_PATH) -> None:
    created_at = ""
    manifest_text = ""
    if manifest_path.exists():
        manifest_text = manifest_path.read_text(encoding="utf-8")
        try:
            m = json.loads(manifest_text)
            created_at = m.get("ended_at", "")
        except Exception:
            created_at = ""
    db.execute("INSERT INTO snapshots (created_at, manifest_json) VALUES (?, ?)", (created_at, manifest_text))
    db.commit()


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Import JSONL corpus into SQLite with FTS5.")
    p.add_argument("--corpus", default=None, help="Path to main corpus JSONL")
    p.add_argument("--game-files", default=None, help="Path to game file corpus JSONL")
    p.add_argument("--all", action="store_true", help="Import both corpus and game files")
    args = p.parse_args()

    corpus = args.corpus or (CORPUS_PATH if args.all else None)
    game = args.game_files or (GAME_CORPUS_PATH if args.all else None)

    if not corpus and not game:
        corpus = CORPUS_PATH if CORPUS_PATH.exists() else None
        game = GAME_CORPUS_PATH if GAME_CORPUS_PATH.exists() else None

    if DB_PATH.exists():
        DB_PATH.unlink()

    db = get_db()
    init_db(db)

    total = 0
    if corpus and corpus.exists():
        records = iter_jsonl(corpus)
        n = insert_records(db, records)
        print(f"Corpus: {n} records from {corpus}")
        total += n

    if game and game.exists():
        records = iter_jsonl(game)
        n = insert_records(db, records)
        print(f"Game files: {n} records from {game}")
        total += n

    rebuild_fts(db)
    record_snapshot(db)

    # Stats
    row = db.execute("SELECT COUNT(*) FROM records").fetchone()
    print(f"Total records in DB: {row[0]}")
    row = db.execute("SELECT authority_tier, COUNT(*) FROM records GROUP BY authority_tier ORDER BY COUNT(*) DESC").fetchall()
    for tier, count in row:
        print(f"  {tier}: {count}")

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
