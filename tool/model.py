"""Shared paths, vocabulary and loaders for prova.

Prova is a claim-verification layer for a developer portfolio: every statement
about a project must cite a file that exists in that project's repository at the
recorded commit. Nothing here enforces that — `tool/validate.py` does.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "cases"
EVIDENCE_DIR = ROOT / "evidence"
BUILD_DIR = ROOT / "build"

# The vocabulary a case may claim to sit in. Closed on purpose: a free-text
# pillar list drifts into adjectives, and adjectives are what this project
# exists to avoid.
PILLARS: dict[str, str] = {
    "messaging": "Event and message transport",
    "distributed-systems": "Multi-service coordination and failure handling",
    "realtime": "Live, stateful client-server interaction",
    "fullstack": "End-to-end product delivery",
    "platform": "Deployment, infrastructure and operations",
    "ai": "LLM-integrated product engineering",
    "security": "Authentication, authorisation and data protection",
    "data": "Persistence, query and retrieval",
    "tooling": "Developer tooling and automation",
}

REQUIRED_FIELDS = (
    "id",
    "name",
    "repo",
    "tagline",
    "role",
    "period",
    "pillars",
    "stack",
    "problem",
    "approach",
    "claims",
    "decisions",
    "verification",
    "limits",
)

CLAIM_MAX_CHARS = 280


def evidence_path(repo: str) -> Path:
    """Evidence files are named after owner and repo, since '/' cannot be in a name."""
    return EVIDENCE_DIR / (repo.replace("/", "__") + ".json")


def load_cases() -> list[dict]:
    """Load every case file, sorted, annotated with its filename.

    A file that does not parse to a mapping is returned wrapped so the validator
    can report it rather than the loader dying with a traceback.
    """
    cases: list[dict] = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not isinstance(data, dict):
            data = {"_invalid": data}
        data["_file"] = path.name
        data["_stem"] = path.stem
        cases.append(data)
    return cases


def load_evidence(repo: str) -> dict | None:
    path = evidence_path(repo)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_test_path(path: str) -> bool:
    """Whether a path looks like a test or spec, across the stacks in use here."""
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith(("test/", "tests/", "spec/"))
        or "/test/" in path
        or "/tests/" in path
        or "/__tests__/" in path
        or ".test." in name
        or ".spec." in name
        or name.endswith(("Test.java", "Tests.java", "Test.kt", "Tests.kt"))
    )
