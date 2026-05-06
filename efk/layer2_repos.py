from __future__ import annotations

import os
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import LAYER2_REPOS, RepoSpec
from .records import authority_flags, sha256_hex, utc_now_iso
from .markdown import parse_frontmatter, extract_title, extract_headings, strip_markdown, extract_outlinks


def run_git(args: List[str], *, cwd: Path) -> None:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def git_stdout(args: List[str], *, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc.stdout.strip()


def ensure_repo_cloned(repo: RepoSpec, *, repos_dir: Path) -> Path:
    repos_dir = repos_dir.resolve()
    repos_dir.mkdir(parents=True, exist_ok=True)
    owner, name = repo.slug.split("/", 1)
    target = repos_dir / owner / name
    if (target / ".git").exists():
        return target

    if target.exists():
        # A previous run may have created the folder but failed mid-clone.
        # Remove it so git can clone cleanly.
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{repo.slug}.git"
    run_git(["clone", "--depth", "1", url, str(target)], cwd=repos_dir)
    return target


TEXT_EXTS = {
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".lock",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".move",
    ".sol",
    ".sh",
    ".ps1",
    ".proto",
    ".graphql",
    ".gql",
    ".env.example",
}


def looks_textual(path: Path) -> bool:
    if path.name.startswith("."):
        # still allow some dotfiles
        return path.suffix in TEXT_EXTS or path.name in {"README", "LICENSE", "NOTICE"}
    if path.suffix in TEXT_EXTS:
        return True
    if path.name in {"README.md", "LICENSE", "NOTICE"}:
        return True
    return False


def safe_read_text(path: Path) -> str:
    # Avoid choking on odd encodings.
    return path.read_text(encoding="utf-8", errors="replace")


def infer_repo_categories(rel_path: str, default_categories: Tuple[str, ...]) -> List[str]:
    p = rel_path.replace("\\", "/").lower()
    cats = set(default_categories)

    if "package" in p or "pnpm-lock" in p or "package-lock" in p or "cargo.lock" in p:
        cats.add("package-versioning")
    if "dapp" in p:
        cats.add("dapp-kit")
    if "gate" in p:
        cats.add("smart-gates")
    if "assembly" in p:
        cats.add("smart-assemblies")
    if "wallet" in p or "vault" in p:
        cats.add("wallet")
    if "identity" in p or "login" in p or "auth" in p:
        cats.add("identity")
    if "index" in p or "search" in p:
        cats.add("indexing")
    if "tool" in p or "cli" in p:
        cats.add("tooling")

    return sorted(cats)


def repo_record_id(repo_slug: str, rel_path: str) -> str:
    return sha256_hex(f"{repo_slug}:{rel_path}".encode("utf-8"))


def scrape_layer2_repos(*, repos_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    per_repo_counts: Dict[str, int] = {}

    for repo in LAYER2_REPOS:
        try:
            repo_path = ensure_repo_cloned(repo, repos_dir=repos_dir)
        except Exception as e:  # noqa: BLE001
            failures.append({"repo": repo.slug, "stage": "clone", "error": repr(e)})
            continue

        try:
            commit = git_stdout(["rev-parse", "HEAD"], cwd=repo_path)
        except Exception as e:  # noqa: BLE001
            commit = ""
            failures.append({"repo": repo.slug, "stage": "rev-parse", "error": repr(e)})

        count = 0
        for root, dirs, files in os.walk(repo_path):
            # prune common large folders
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "target", "dist", "build", ".next"}]

            for fn in files:
                path = Path(root) / fn
                if not looks_textual(path):
                    continue

                rel = str(path.relative_to(repo_path)).replace("\\", "/")
                try:
                    raw = safe_read_text(path)
                    content_hash = sha256_hex(raw.encode("utf-8"))
                    cats = infer_repo_categories(rel, repo.default_source_categories)
                    ext = path.suffix.lower()

                    rec = {
                        "id": repo_record_id(repo.slug, rel),
                        "slug_id": f"repo:{repo.slug}:{rel}",
                        "source": "repo",
                        "source_repo": repo.slug,
                        "source_ref": "HEAD",
                        "source_commit": commit,
                        "authority_tier": repo.authority_tier,
                        "authority": authority_flags(repo.authority_tier),
                        "url": f"repo://{repo.slug}/{rel}",
                        "path": f"/{repo.slug}/{rel}",
                        "file_extension": ext,
                        "retrieved_at": utc_now_iso(),
                        "title": fn,
                        "category": "unknown",
                        "source_categories": cats,
                        "frontmatter": {},
                        "headings": [],
                        "outlinks": [],
                        "content_sha256": content_hash,
                        "raw_markdown": raw,
                        "text": raw,
                    }
                    # Parse markdown for .md/.mdx files to populate frontmatter/headings/title/text
                    if ext in {".md", ".mdx"}:
                        try:
                            fm, rest = parse_frontmatter(raw)
                            title = fm.get("title") or extract_title(rest) or rec["title"]
                            headings = extract_headings(rest)
                            text = strip_markdown(rest)
                            outlinks = extract_outlinks(raw, page_url=rec["url"]) if raw else []
                            rec["frontmatter"] = fm
                            rec["headings"] = headings
                            rec["title"] = title
                            rec["text"] = text
                            rec["outlinks"] = outlinks
                        except Exception:
                            # keep fallback values on parse errors
                            pass
                    records.append(rec)
                    count += 1
                except Exception as e:  # noqa: BLE001
                    failures.append({"repo": repo.slug, "path": rel, "stage": "read", "error": repr(e)})

        per_repo_counts[repo.slug] = count

    fragment = {
        "layer": "layer2_repos",
        "repos": [r.slug for r in LAYER2_REPOS],
        "per_repo_counts": per_repo_counts,
        "records": len(records),
        "failures": failures,
    }
    return records, fragment

