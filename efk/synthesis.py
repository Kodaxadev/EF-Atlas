from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def write_md(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _record_link(rec: Dict[str, Any]) -> str:
    # Use url field as canonical pointer (https://... or repo://...)
    title = rec.get("title") or rec.get("slug_id") or rec.get("url")
    url = rec.get("url", "")
    return f"- {title} (`{url}`)"


def _section(title: str, lines: Iterable[str]) -> str:
    lines_list = [ln for ln in lines if ln]
    if not lines_list:
        lines_list = ["- (none found)"]
    return "\n".join([f"## {title}", *lines_list, ""])


def generate_builder_truth_index(records: List[Dict[str, Any]]) -> str:
    header = "\n".join(
        [
            "# EVE Frontier Builder Knowledge Corpus",
            "",
            "This index is generated from the local corpus JSONL.",
            "It lists sources and how they are labeled (authority tiers) without adding conclusions.",
            "",
        ]
    )

    # Authority buckets
    by_tier: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        tier = str(r.get("authority_tier", "unofficial"))
        by_tier.setdefault(tier, []).append(r)

    parts = [header]
    for tier in sorted(by_tier.keys()):
        # show a small sample of URLs, plus counts
        sample = sorted({str(r.get("url", "")) for r in by_tier[tier] if r.get("url")})[:20]
        lines = [f"- **count**: {len(by_tier[tier])}"] + [f"- `{u}`" for u in sample]
        parts.append(_section(f"Authority: {tier}", lines))

    return "\n".join(parts).rstrip() + "\n"


def generate_topic_doc(records: List[Dict[str, Any]], *, title: str, category_key: str) -> str:
    header = "\n".join(
        [
            f"# {title}",
            "",
            "Generated from the local corpus JSONL.",
            "Entries are grouped by authority tier and list URLs only.",
            "",
        ]
    )

    matched = [r for r in records if category_key in (r.get("source_categories") or [])]
    by_tier: Dict[str, List[Dict[str, Any]]] = {}
    for r in matched:
        by_tier.setdefault(str(r.get("authority_tier", "unofficial")), []).append(r)

    parts = [header]
    for tier in sorted(by_tier.keys()):
        lines = [_record_link(r) for r in by_tier[tier][:200]]
        parts.append(_section(f"{tier}", lines))

    return "\n".join(parts).rstrip() + "\n"


def generate_dapp_index_doc(records: List[Dict[str, Any]]) -> str:
    header = "\n".join(
        [
            "# dapp-index Repo Synthesis",
            "",
            "Generated from the local corpus JSONL.",
            "Covers only `evefrontier/dapp-index` files.",
            "",
        ]
    )

    repo_recs = [r for r in records if r.get("source_repo") == "evefrontier/dapp-index"]

    def _match(keywords: List[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in repo_recs:
            p = (r.get("path") or "").lower()
            if any(k in p for k in keywords):
                out.append(r)
        return out

    readme = _match(["readme"])
    builder_plan = _match(["builder_plan", "builder-plan"])
    registry_pkg = _match(["registry-move/", "registry/move.toml", "registry/move.lock", "registry/sources", "registry/tests"])
    registry_publish = _match(["move_publish", "move-publish"])
    metadata_model = _match(["metadata"])
    discussion = _match(["discussion", "watch", "notes"])

    parts = [header]
    parts.append(_section("README", [_record_link(r) for r in readme]))
    parts.append(_section("docs/BUILDER_PLAN", [_record_link(r) for r in builder_plan]))
    parts.append(_section("Registry / Package Files (registry-move/)", [_record_link(r) for r in registry_pkg]))
    parts.append(_section("docs/MOVE_PUBLISH.md", [_record_link(r) for r in registry_publish]))
    parts.append(_section("Metadata Model Files", [_record_link(r) for r in metadata_model]))
    parts.append(_section("Discussion / Watch Notes", [_record_link(r) for r in discussion]))

    return "\n".join(parts).rstrip() + "\n"


def write_synthesis(out_dir: Path, corpus_jsonl: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = load_jsonl(corpus_jsonl)

    write_md(out_dir / "builder_truth_index.md", generate_builder_truth_index(records))
    write_md(out_dir / "smart_gates.md", generate_topic_doc(records, title="Smart Gates", category_key="smart-gates"))
    write_md(
        out_dir / "package_versioning.md",
        generate_topic_doc(records, title="Package Versioning", category_key="package-versioning"),
    )
    write_md(out_dir / "identity.md", generate_topic_doc(records, title="Identity", category_key="identity"))
    write_md(
        out_dir / "dapp_discovery.md",
        generate_topic_doc(records, title="dApp Discovery", category_key="discovery"),
    )
    write_md(out_dir / "tooling.md", generate_topic_doc(records, title="Tooling", category_key="tooling"))
    write_md(out_dir / "dapp_index.md", generate_dapp_index_doc(records))

