"""The evidence refresh must be all-or-nothing.

Each evidence file pins a commit. If a refresh writes some files and then fails,
the corpus is *mixed* — some repositories at the new head, some at the old — and
`make verify` accepts it, because every file is internally consistent. Half the
catalogue would then pin commits nobody re-checked.
"""

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

TOOL = Path(__file__).resolve().parent.parent / "tool"
sys.path.insert(0, str(TOOL))

import collect  # noqa: E402


def fake_record(repo: str) -> dict:
    return {
        "repo": repo,
        "collected_at": "2026-01-01T00:00:00Z",
        "default_branch": "main",
        "private": False,
        "head_sha": "0" * 40,
        "head_date": "2026-01-01T00:00:00Z",
        "pushed_at": "2026-01-01T00:00:00Z",
        "homepage": None,
        "primary_language": "Python",
        "languages": {"Python": 1},
        "file_count": 1,
        "tree_truncated": False,
        "paths": ["README.md"],
        "shape": {"ci_workflows": [], "tests": [], "terraform": [], "containers": [], "docs": []},
    }


CASES = [
    {"id": "alpha", "repo": "example/alpha"},
    {"id": "beta", "repo": "example/beta"},
]


class CollectAtomicityTests(unittest.TestCase):
    def run_collect(self, evidence_dir: Path, failing: set[str]) -> int:
        def fake_collect(repo: str, _token: str | None) -> dict:
            if repo in failing:
                raise RuntimeError(f"{repo} -> HTTP 502")
            return fake_record(repo)

        with (
            patch.object(collect, "load_cases", return_value=CASES),
            patch.object(collect, "EVIDENCE_DIR", evidence_dir),
            # `evidence_path` resolves against the model module's constant, not the
            # name collect imported alongside it.
            patch("model.EVIDENCE_DIR", evidence_dir),
            patch.object(collect, "resolve_token", return_value="token"),
            patch.object(collect, "collect_repo", side_effect=fake_collect),
        ):
            return collect.main()

    def test_a_failed_refresh_writes_nothing(self):
        with TemporaryDirectory() as directory:
            evidence_dir = Path(directory)

            code = self.run_collect(evidence_dir, failing={"example/beta"})

            self.assertEqual(code, 1)
            self.assertEqual(
                list(evidence_dir.glob("*.json")),
                [],
                "a partial refresh must not leave a mixed corpus behind",
            )

    def test_a_complete_refresh_writes_every_file(self):
        with TemporaryDirectory() as directory:
            evidence_dir = Path(directory)

            code = self.run_collect(evidence_dir, failing=set())

            self.assertEqual(code, 0)
            written = sorted(p.name for p in evidence_dir.glob("*.json"))
            self.assertEqual(written, ["example__alpha.json", "example__beta.json"])
            payload = json.loads((evidence_dir / "example__alpha.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["repo"], "example/alpha")

    def test_no_temp_files_are_left_behind(self):
        with TemporaryDirectory() as directory:
            evidence_dir = Path(directory)

            self.run_collect(evidence_dir, failing=set())

            self.assertEqual(list(evidence_dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
