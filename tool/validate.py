#!/usr/bin/env python3
"""Verify every claim in cases/ against the evidence recorded from GitHub.

The rule, in one sentence: a claim about a project is only allowed if it cites at
least one path in that project's repository, and every cited path must actually
exist at the recorded commit.

A claim that cannot be traced is an error, not a warning. Warnings are reserved
for things that are legal but weak: overclaiming vocabulary, a claim long enough
to hide behind, or verification that never points at anything executable.

Exit status: 0 clean, 1 errors.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import (  # noqa: E402
    CLAIM_MAX_CHARS,
    PILLARS,
    REQUIRED_FIELDS,
    is_test_path,
    load_cases,
    load_evidence,
)

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Words that do work the evidence should be doing. Matched case-insensitively
# anywhere in prose fields; each hit is a warning, never a hard failure, because
# context can make a phrase legitimate.
OVERCLAIM = (
    "world-class",
    "cutting-edge",
    "best-in-class",
    "revolutionary",
    "unparalleled",
    "rockstar",
    "ninja",
    "guru",
    "10x",
    "visionary",
    "passionate about",
    "thought leader",
    "state-of-the-art",
    "bleeding edge",
    "game-changing",
)

PROSE_PATHS = ("tagline", "problem")


def resolve_citation(cite: str, paths: list[str]) -> list[str]:
    """Resolve a citation to real file paths.

    Supported forms: an exact path, a directory prefix ending in '/', or a glob.
    An exact match always wins, because real paths in this codebase contain
    characters that glob syntax also uses: Next.js route segments such as
    `app/api/status/[slug]/events/route.ts` would otherwise be interpreted as a
    character class and silently fail to resolve.
    """
    if cite in paths:
        return [cite]
    if cite.endswith("/"):
        return sorted(path for path in paths if path.startswith(cite))
    if any(token in cite for token in "*?["):
        return sorted(fnmatch.filter(paths, cite))
    return []


def prose_fragments(case: dict):
    """Yield (label, text) for every human-readable field, for the wording lint."""
    for key in PROSE_PATHS:
        value = case.get(key)
        if isinstance(value, str):
            yield key, value
    for index, item in enumerate(case.get("approach") or []):
        if isinstance(item, dict):
            for key in ("title", "body"):
                if isinstance(item.get(key), str):
                    yield f"approach[{index}].{key}", item[key]
    for index, claim in enumerate(case.get("claims") or []):
        if isinstance(claim, dict) and isinstance(claim.get("text"), str):
            yield f"claims[{index}].text", claim["text"]
    for index, decision in enumerate(case.get("decisions") or []):
        if isinstance(decision, dict):
            for key in ("chose", "rejected", "why"):
                if isinstance(decision.get(key), str):
                    yield f"decisions[{index}].{key}", decision[key]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.lines: list[str] = []
        self.claims = 0
        self.citations = 0
        self.resolved = 0
        self.tests_cited = 0

    def error(self, case: str, message: str) -> None:
        self.errors.append(f"{case}: {message}")

    def warn(self, case: str, message: str) -> None:
        self.warnings.append(f"{case}: {message}")


def check_citations(
    report: Report, label: str, where: str, citations, paths: list[str]
) -> None:
    if not isinstance(citations, list) or not citations:
        report.error(label, f"{where} has no citation; every claim must cite a file")
        return
    for raw in citations:
        if not isinstance(raw, str) or not raw.strip():
            report.error(label, f"{where} contains an empty citation")
            continue
        cite = raw.strip()
        report.citations += 1
        matches = resolve_citation(cite, paths)
        if not matches:
            report.error(
                label,
                f'{where} cites "{cite}", which is not in the repository at the recorded commit',
            )
            continue
        report.resolved += 1
        if any(is_test_path(path) for path in matches):
            report.tests_cited += 1


def check_case(case: dict, report: Report, seen_ids: set[str], seen_stems: set[str]) -> None:
    stem = case.get("_stem") or "<unknown>"
    label = stem

    if "_invalid" in case:
        report.error(label, f"{case['_file']} does not contain a mapping")
        return

    missing = [field for field in REQUIRED_FIELDS if field not in case]
    if missing:
        report.error(label, f"missing required field(s): {', '.join(missing)}")
        return

    # ---------------------------------------------------------------- identity
    case_id = case.get("id")
    if not isinstance(case_id, str) or not ID_PATTERN.match(case_id):
        report.error(label, "id must match ^[a-z0-9][a-z0-9-]*$")
    elif case_id != stem:
        report.error(label, f"id is '{case_id}' but the filename is '{stem}.yaml'")
    elif case_id in seen_ids:
        report.error(label, f"duplicate case id '{case_id}'")
    else:
        seen_ids.add(case_id)
        seen_stems.add(stem)

    # ------------------------------------------------------------------- repo
    repo = case.get("repo")
    evidence = None
    if not isinstance(repo, str) or not REPO_PATTERN.match(repo):
        report.error(label, "repo must be owner/name")
    else:
        evidence = load_evidence(repo)
        if evidence is None:
            report.error(label, f"no evidence for {repo}; run `make evidence`")

    paths: list[str] = list(evidence.get("paths", [])) if evidence else []
    sha = (evidence or {}).get("head_sha") or "unknown"
    if evidence and evidence.get("tree_truncated"):
        report.warn(label, "the recorded tree is truncated; later paths may be unresolvable")

    # The whole premise is that a reader can open a citation and see the file.
    # A private repository makes every citation in this case unopenable to that
    # reader, which is worse than an unverified claim: it looks checkable and is
    # not. Collection needs a token with private scope to have got this far, so
    # this is caught here rather than trusted to the collector's permissions.
    if evidence and evidence.get("private"):
        report.error(
            label,
            f"{repo} is a private repository, so no citation here can be opened by a "
            "reader; make it public or remove the case",
        )

    # --------------------------------------------------------------- prose
    for key in ("tagline", "role", "period", "problem"):
        value = case.get(key)
        if not isinstance(value, str) or not value.strip():
            report.error(label, f"{key} must be a non-empty string")

    # Optional, but when present it must be real: a bilingual site that silently
    # falls back to English on its Portuguese route is a defect, not a default.
    if "tagline_pt" in case:
        value = case.get("tagline_pt")
        if not isinstance(value, str) or len(value.strip()) < 20:
            report.error(label, "tagline_pt must be at least 20 chars when present")
    else:
        report.warn(label, "no tagline_pt; the portfolio's /pt route will show English copy")

    pillars = case.get("pillars")
    if not isinstance(pillars, list) or not pillars:
        report.error(label, "pillars must be a non-empty list")
    else:
        for pillar in pillars:
            if pillar not in PILLARS:
                report.error(
                    label,
                    f"unknown pillar '{pillar}'; allowed: {', '.join(sorted(PILLARS))}",
                )

    stack = case.get("stack")
    if not isinstance(stack, list) or not stack:
        report.error(label, "stack must be a non-empty list")
    elif not all(isinstance(item, str) and item.strip() for item in stack):
        report.error(label, "stack entries must be non-empty strings")

    # -------------------------------------------------------------- approach
    approach = case.get("approach")
    if not isinstance(approach, list) or not approach:
        report.error(label, "approach must be a non-empty list")
    else:
        for index, item in enumerate(approach):
            if not isinstance(item, dict):
                report.error(label, f"approach[{index}] must be a mapping")
                continue
            for key, minimum in (("title", 3), ("body", 40)):
                value = item.get(key)
                if not isinstance(value, str) or len(value.strip()) < minimum:
                    report.error(
                        label, f"approach[{index}].{key} must be at least {minimum} chars"
                    )

    # ---------------------------------------------------------------- claims
    claims = case.get("claims")
    tests_at_entry = report.tests_cited
    if not isinstance(claims, list) or not claims:
        report.error(label, "claims must be a non-empty list")
    else:
        seen_claim_ids: set[str] = set()
        for index, claim in enumerate(claims):
            where = f"claims[{index}]"
            if not isinstance(claim, dict):
                report.error(label, f"{where} must be a mapping")
                continue
            claim_id = claim.get("id")
            if not isinstance(claim_id, str) or not ID_PATTERN.match(claim_id):
                report.error(label, f"{where}.id must match ^[a-z0-9][a-z0-9-]*$")
            elif claim_id in seen_claim_ids:
                report.error(label, f"{where}.id '{claim_id}' is duplicated in this case")
            else:
                seen_claim_ids.add(claim_id)

            text = claim.get("text")
            if not isinstance(text, str) or len(text.strip()) < 20:
                report.error(label, f"{where}.text must be at least 20 chars")
            elif len(text) > CLAIM_MAX_CHARS:
                report.error(
                    label,
                    f"{where}.text is {len(text)} chars; "
                    f"a claim must stay under {CLAIM_MAX_CHARS} to remain checkable",
                )

            report.claims += 1
            check_citations(report, label, f"{where}.cite", claim.get("cite"), paths)

    # ------------------------------------------------------------- decisions
    decisions = case.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        report.error(label, "decisions must be a non-empty list")
    else:
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict):
                report.error(label, f"decisions[{index}] must be a mapping")
                continue
            # A decision with no rejected alternative is marketing.
            for key, minimum in (("chose", 10), ("rejected", 3), ("why", 40)):
                value = decision.get(key)
                if not isinstance(value, str) or len(value.strip()) < minimum:
                    report.error(
                        label, f"decisions[{index}].{key} must be at least {minimum} chars"
                    )

    # ----------------------------------------------------------- verification
    verification = case.get("verification")
    if not isinstance(verification, list) or not verification:
        report.error(label, "verification must be a non-empty list")
    else:
        for index, item in enumerate(verification):
            where = f"verification[{index}]"
            if not isinstance(item, dict):
                report.error(label, f"{where} must be a mapping")
                continue
            what = item.get("what")
            if not isinstance(what, str) or len(what.strip()) < 15:
                report.error(label, f"{where}.what must be at least 15 chars")
            check_citations(report, label, f"{where}.cite", item.get("cite"), paths)

    # ---------------------------------------------------------------- limits
    limits = case.get("limits")
    if not isinstance(limits, list) or not limits:
        report.error(
            label,
            "limits must be non-empty: a project with no stated limits has not been examined",
        )
    else:
        for index, limit in enumerate(limits):
            if not isinstance(limit, str) or len(limit.strip()) < 20:
                report.error(label, f"limits[{index}] must be at least 20 chars")

    # ----------------------------------------------------------------- lint
    for where, text in prose_fragments(case):
        lowered = text.lower()
        for phrase in OVERCLAIM:
            if phrase in lowered:
                report.warn(label, f'{where} contains "{phrase}", which the evidence cannot support')

    if report.tests_cited == tests_at_entry:
        report.warn(label, "neither claims nor verification cite a test or spec file")

    # ----------------------------------------------------------------- stats
    report.lines.append(
        f"  {label:<20} {(repo or '-'):<28} @ {sha[:8]:<9} "
        f"claims {len(claims) if isinstance(claims, list) else 0:>2}  "
        f"decisions {len(decisions) if isinstance(decisions, list) else 0:>2}  "
        f"limits {len(limits) if isinstance(limits, list) else 0:>2}"
    )


def main() -> int:
    cases = load_cases()
    report = Report()

    print(f"prova - verifying {len(cases)} case(s) against recorded evidence\n")

    if not cases:
        print("no case files found in cases/", file=sys.stderr)
        return 1

    seen_ids: set[str] = set()
    seen_stems: set[str] = set()
    for case in cases:
        check_case(case, report, seen_ids, seen_stems)

    print("\n".join(report.lines))
    print(
        f"\ncitations  {report.resolved}/{report.citations} resolved  ·  "
        f"claims {report.claims}  ·  citations to tests {report.tests_cited}"
    )

    if report.warnings:
        print(f"\nwarnings ({len(report.warnings)}):")
        for warning in report.warnings:
            print(f"  WARN  {warning}")

    if report.errors:
        print(f"\nERRORS ({len(report.errors)}):")
        for error in report.errors:
            print(f"  FAIL  {error}")
        print("\nFAIL - an untraceable claim is not allowed on the page.")
        return 1

    print("\nPASS - every citation resolves to a file at the recorded commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
