#!/usr/bin/env python3
"""Collect repository evidence from GitHub into evidence/<owner>__<repo>.json.

For every repository named in cases/, this records what is actually present at a
fixed commit: the full file tree, languages, head SHA and date, and a few shape
facts (CI, container, Terraform, tests). The output is committed, so:

  * verification runs offline and identically on any machine
  * a reviewer can diff what the claims were checked against
  * a repository that changes underneath a claim shows up as drift, not silence

Authentication: GITHUB_TOKEN / GH_TOKEN, or the `gh` CLI's stored token.
Public repositories work unauthenticated but are rate-limited to 60 requests
per hour, which is not enough for a full refresh.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import CASES_DIR, EVIDENCE_DIR, evidence_path, is_test_path, load_cases  # noqa: E402

API = "https://api.github.com"


def resolve_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value.strip()
    if shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=True
            )
            return result.stdout.strip() or None
        except (subprocess.CalledProcessError, OSError):
            return None
    return None


def request(path: str, token: str | None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "prova-evidence/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API}{path}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=45
        ) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:240]
        raise RuntimeError(f"{url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} -> {exc.reason}") from exc


def classify(paths: list[str]) -> dict[str, list[str]]:
    """Shape facts derived from the tree. Used for rendering, never for claims."""
    ci = [p for p in paths if p.startswith(".github/workflows/")]
    tests = [p for p in paths if is_test_path(p)]
    terraform = [p for p in paths if p.endswith(".tf")]
    return {
        "ci_workflows": ci,
        "tests": tests,
        "terraform": terraform,
        "containers": [
            p
            for p in paths
            if p.endswith(("Dockerfile", ".dockerignore"))
            or p in ("docker-compose.yml", "compose.yml", "compose.yaml")
        ],
        "docs": [p for p in paths if p.startswith("docs/") and p.endswith(".md")],
    }


def collect_repo(repo: str, token: str | None) -> dict:
    meta = request(f"/repos/{repo}", token)
    branch = meta.get("default_branch") or "main"

    tree = request(f"/repos/{repo}/git/trees/{branch}?recursive=1", token)
    paths = sorted(
        entry["path"] for entry in tree.get("tree", []) if entry.get("type") == "blob"
    )

    commits = request(f"/repos/{repo}/commits?per_page=1", token)
    head = commits[0] if isinstance(commits, list) and commits else {}

    languages = request(f"/repos/{repo}/languages", token)

    return {
        "repo": repo,
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "default_branch": branch,
        # Recorded because it decides whether a citation is checkable by a reader
        # at all. The validator refuses cases whose repository is not public.
        "private": bool(meta.get("private", False)),
        "head_sha": head.get("sha"),
        "head_date": (head.get("commit", {}).get("committer", {}) or {}).get("date"),
        "pushed_at": meta.get("pushed_at"),
        "homepage": meta.get("homepage") or None,
        "primary_language": meta.get("language"),
        "languages": languages if isinstance(languages, dict) else {},
        "file_count": len(paths),
        "tree_truncated": bool(tree.get("truncated")),
        "paths": paths,
        "shape": classify(paths),
    }


def main() -> int:
    token = resolve_token()
    if not token:
        print(
            "warning: no GitHub token found; unauthenticated requests are limited to "
            "60/hour and this refresh will probably fail partway.\n"
            "         export GITHUB_TOKEN=... or authenticate with `gh auth login`.",
            file=sys.stderr,
        )

    cases = load_cases()
    if not cases:
        print(f"no case files in {CASES_DIR}", file=sys.stderr)
        return 1

    repos: dict[str, str] = {}
    for case in cases:
        repo = case.get("repo")
        if isinstance(repo, str) and "/" in repo:
            repos[repo] = case.get("id") or case.get("name") or repo

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    failures = 0
    for repo, label in sorted(repos.items()):
        try:
            record = collect_repo(repo, token)
        except RuntimeError as exc:
            print(f"  FAIL {label:<20} {exc}", file=sys.stderr)
            failures += 1
            continue
        destination = evidence_path(repo)
        destination.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(
            f"  {label:<20} {record['head_sha'][:8] if record['head_sha'] else 'unknown':<10} "
            f"{record['file_count']:>4} paths  "
            f"{len(record['shape']['tests']):>2} tests  "
            f"{len(record['shape']['ci_workflows'])} CI"
        )

    if failures:
        print(f"\n{failures} repository/repositories could not be collected.", file=sys.stderr)
        return 1
    print(f"\nwrote {len(repos)} evidence file(s) to {EVIDENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
