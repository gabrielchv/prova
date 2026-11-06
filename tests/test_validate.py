"""Tests for the claim validator.

The validator is the point of this repository, so it is the thing that gets
tested. Each test builds a minimal valid case, breaks exactly one rule, and
asserts that the break is caught. A rule that cannot fail in a test is not
enforced anywhere.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL = Path(__file__).resolve().parent.parent / "tool"
sys.path.insert(0, str(TOOL))

import validate  # noqa: E402

EVIDENCE = {
    "repo": "example/demo",
    "head_sha": "0" * 40,
    "tree_truncated": False,
    "paths": [
        "README.md",
        "docs/architecture.md",
        "src/backoff.ts",
        "src/signature.ts",
        "tests/backoff.test.ts",
        "k8s/00-namespace.yaml",
    ],
}


def base_case(**overrides):
    case = {
        "id": "demo",
        "name": "demo",
        "repo": "example/demo",
        "tagline": "A tagline long enough to clear the minimum length rule.",
        "tagline_pt": "Uma chamada em português com tamanho suficiente para passar.",
        "role": "Independent build of the whole thing.",
        "period": "2026-11",
        "pillars": ["messaging"],
        "stack": ["TypeScript"],
        "problem": "A problem statement that comfortably exceeds forty characters.",
        "approach": [
            {
                "title": "One idea",
                "body": "A body long enough to clear the forty character minimum.",
            }
        ],
        "claims": [
            {
                "id": "one",
                "text": "A claim that is at least twenty characters long.",
                "cite": ["src/backoff.ts"],
            }
        ],
        "decisions": [
            {
                "chose": "Chose the first approach",
                "rejected": "The other one",
                "why": "Because the other one fails under concurrency, which is the whole point.",
            }
        ],
        "verification": [
            {"what": "Unit tests cover this path.", "cite": ["tests/backoff.test.ts"]}
        ],
        "limits": ["A stated limit that is honest about what this does not do."],
        "_stem": "demo",
        "_file": "demo.yaml",
    }
    case.update(overrides)
    return case


class CitationResolutionTests(unittest.TestCase):
    PATHS = EVIDENCE["paths"]

    def test_exact_path(self):
        self.assertEqual(validate.resolve_citation("src/backoff.ts", self.PATHS), ["src/backoff.ts"])

    def test_missing_path(self):
        self.assertEqual(validate.resolve_citation("src/nope.ts", self.PATHS), [])

    def test_directory_prefix(self):
        self.assertEqual(validate.resolve_citation("k8s/", self.PATHS), ["k8s/00-namespace.yaml"])

    def test_glob(self):
        self.assertEqual(
            validate.resolve_citation("src/*.ts", self.PATHS),
            ["src/backoff.ts", "src/signature.ts"],
        )

    def test_glob_with_no_match(self):
        self.assertEqual(validate.resolve_citation("src/*.rs", self.PATHS), [])

    def test_bracketed_path_is_literal_not_a_glob(self):
        # Next.js route segments use brackets, which fnmatch reads as a character
        # class. An exact match has to win, or every dynamic route citation fails.
        paths = ["app/api/status/[slug]/events/route.ts", "app/api/healthz/route.ts"]
        self.assertEqual(
            validate.resolve_citation("app/api/status/[slug]/events/route.ts", paths),
            ["app/api/status/[slug]/events/route.ts"],
        )


class RuleTests(unittest.TestCase):
    def run_case(self, case):
        report = validate.Report()
        with patch.object(validate, "load_evidence", return_value=EVIDENCE):
            validate.check_case(case, report, set(), set())
        return report

    def assert_error(self, report, fragment):
        joined = "\n".join(report.errors)
        self.assertTrue(report.errors, "expected an error but the case passed")
        self.assertIn(fragment, joined)

    # ---------------------------------------------------------------- happy path
    def test_valid_case_has_no_errors(self):
        report = self.run_case(base_case())
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    # ------------------------------------------------------------------ citations
    def test_citation_to_missing_file_is_an_error(self):
        case = base_case()
        case["claims"][0]["cite"] = ["src/nope.ts"]
        self.assert_error(self.run_case(case), "not in the repository")

    def test_claim_with_no_citation_is_an_error(self):
        case = base_case()
        case["claims"][0]["cite"] = []
        self.assert_error(self.run_case(case), "has no citation")

    def test_verification_citation_is_checked_too(self):
        case = base_case()
        case["verification"][0]["cite"] = ["tests/missing.test.ts"]
        self.assert_error(self.run_case(case), "not in the repository")

    # --------------------------------------------------------------- honesty rules
    def test_empty_limits_is_an_error(self):
        self.assert_error(self.run_case(base_case(limits=[])), "limits must be non-empty")

    def test_decision_without_rejected_alternative_is_an_error(self):
        case = base_case()
        del case["decisions"][0]["rejected"]
        self.assert_error(self.run_case(case), "rejected")

    def test_overlong_claim_is_an_error(self):
        case = base_case()
        case["claims"][0]["text"] = "x" * (validate.CLAIM_MAX_CHARS + 1)
        self.assert_error(self.run_case(case), "must stay under")

    def test_unknown_pillar_is_an_error(self):
        self.assert_error(self.run_case(base_case(pillars=["synergy"])), "unknown pillar")

    # ------------------------------------------------------------------- identity
    def test_id_must_match_filename(self):
        self.assert_error(self.run_case(base_case(id="other")), "filename")

    def test_duplicate_claim_id_is_an_error(self):
        case = base_case()
        case["claims"].append(dict(case["claims"][0]))
        self.assert_error(self.run_case(case), "duplicated")

    def test_missing_required_field_is_an_error(self):
        case = base_case()
        del case["problem"]
        self.assert_error(self.run_case(case), "missing required field")

    # -------------------------------------------------------------------- warnings
    def test_missing_priorities_are_only_a_warning(self):
        case = base_case()
        del case["tagline_pt"]
        report = self.run_case(case)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("tagline_pt" in warning for warning in report.warnings))

    def test_short_tagline_pt_is_an_error(self):
        report = self.run_case(base_case(tagline_pt="curta demais"))
        self.assert_error(report, "tagline_pt")

    def test_overclaiming_word_produces_a_warning_not_a_failure(self):
        case = base_case(tagline="A world-class tool that clears the length rule easily.")
        report = self.run_case(case)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("world-class" in warning for warning in report.warnings))

    def test_no_test_citation_produces_a_warning(self):
        case = base_case()
        case["claims"][0]["cite"] = ["README.md"]
        case["verification"][0]["cite"] = ["README.md"]
        report = self.run_case(case)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("test or spec" in warning for warning in report.warnings))

    def test_verification_only_test_citation_satisfies_the_rule(self):
        case = base_case()
        case["claims"][0]["cite"] = ["README.md"]
        report = self.run_case(case)
        self.assertEqual(report.errors, [])
        self.assertFalse(any("test or spec" in warning for warning in report.warnings))

    def test_missing_evidence_is_an_error(self):
        report = validate.Report()
        with patch.object(validate, "load_evidence", return_value=None):
            validate.check_case(base_case(), report, set(), set())
        self.assertTrue(any("no evidence" in error for error in report.errors))

    def test_private_repository_is_an_error(self):
        # A citation nobody can open is not evidence; it only looks like evidence.
        private = dict(EVIDENCE, private=True)
        report = validate.Report()
        with patch.object(validate, "load_evidence", return_value=private):
            validate.check_case(base_case(), report, set(), set())
        self.assert_error(report, "private repository")


if __name__ == "__main__":
    unittest.main()
