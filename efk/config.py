from __future__ import annotations

from dataclasses import dataclass

DOCS_SITEMAP_MD = "https://docs.evefrontier.com/sitemap.md"
WHITEPAPER_SITEMAP_MD = "https://whitepaper.evefrontier.com/sitemap.md"

ALLOWED_CORPUS_HOSTS = {
    "docs.evefrontier.com",
    "whitepaper.evefrontier.com",
}

BLOCKED_QUERY_SUBSTRINGS = ("?ask=", "?q=")


@dataclass(frozen=True)
class SourceSpec:
    source: str  # "docs" | "whitepaper"
    sitemap_url: str
    authority_tier: str  # see AUTHORITY_TIERS


AUTHORITY_TIERS = {
    "authoritative_source",
    "official_docs",
    "official_tooling",
    "community_reference",
    "unofficial",
}


LAYER1_SOURCES = [
    SourceSpec(source="docs", sitemap_url=DOCS_SITEMAP_MD, authority_tier="official_docs"),
    SourceSpec(
        source="whitepaper", sitemap_url=WHITEPAPER_SITEMAP_MD, authority_tier="authoritative_source"
    ),
]


@dataclass(frozen=True)
class RepoSpec:
    slug: str  # owner/repo
    authority_tier: str
    default_source_categories: tuple[str, ...]
    pr_branch: str | None = None  # e.g. "pr-2-dapp-registry" for draft PR tracking


LAYER2_REPOS = [
    RepoSpec("evefrontier/world-contracts", "authoritative_source", ("world", "tooling")),
    RepoSpec("evefrontier/builder-documentation", "official_docs", ("tooling", "indexing")),
    RepoSpec("evefrontier/builder-scaffold", "official_tooling", ("tooling", "dapp-kit")),
    RepoSpec("evefrontier/evevault", "official_tooling", ("wallet", "identity", "tooling")),
    RepoSpec(
        "evefrontier/dapp-index",
        "official_tooling",
        ("indexing", "discovery", "tooling"),
        pr_branch="pr-2-dapp-registry",
    ),
]

