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

# Everything a case file may contain. A key outside this set is almost always a
# typo (`limts`, `tagline_ptt`), and a silently ignored field is a rule that was
# meant to be enforced and is not.
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS) | frozenset(
    {
        "tagline_pt",
        "live_url",
        # Added by the loader, not by the author.
        "_file",
        "_stem",
        "_invalid",
        "_error",
    }
)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys.

    `yaml.safe_load` resolves a repeated key by keeping the last one and saying
    nothing. In a case file that means a `claims:` block pasted twice silently
    discards the first set — the validator then certifies a case that is missing
    half its claims, which is the exact failure this project exists to prevent.
    """

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def evidence_path(repo: str) -> Path:
    """Evidence files are named after owner and repo, since '/' cannot be in a name."""
    return EVIDENCE_DIR / (repo.replace("/", "__") + ".json")


def load_cases() -> list[dict]:
    """Load every case file, sorted, annotated with its filename.

    A file that does not parse to a mapping is returned wrapped so the validator
    can report it rather than the loader dying with a traceback. The same applies
    to a file that does not parse at all — a duplicate key is a defect in the
    case, and it is reported as one, against the file, instead of aborting the
    whole run.
    """
    cases: list[dict] = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.load(handle, Loader=_StrictLoader)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            where = f" (line {mark.line + 1})" if mark else ""
            data = {"_error": f"does not parse{where}: {error.__class__.__name__}: {error}"}
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
