"""Recognising a test file, across every stack this repository cites.

The predicate decides two things: whether a claim cites an executable check at
all, and which paths land in the collected `tests` shape facts. A false negative
produces a warning on a case that *does* cite its tests — noise that teaches
people to ignore warnings.
"""

import sys
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tool"
sys.path.insert(0, str(TOOL))

from model import is_test_path  # noqa: E402


class IsTestPathTests(unittest.TestCase):
    def test_recognises_every_stack_in_use_here(self):
        for path in (
            "tests/test_validate.py",
            "src/foo_test.py",
            "tool/test_validate.py",  # missed before, in this very repository
            "src/__tests__/a.ts",
            "lib/a.spec.js",
            "app/routes.test.tsx",
            "backend/src/test/java/A/FooTest.java",
            "e2e/status.spec.ts",
            "spec/models/user_spec.rb",
            "internal/queue_test.go",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_test_path(path))

    def test_does_not_call_ordinary_source_a_test(self):
        for path in (
            "src/app/api/route.ts",
            "lib/fill/orchestrate.ts",
            "README.md",
            "contest/rules.md",
            "src/testimonials.ts",
            "app/testing-notes.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_test_path(path))

    def test_a_test_directory_at_any_depth_counts(self):
        for path in (
            "packages/shared/test/a.ts",
            "services/api/tests/b.py",
            "modules/x/__tests__/c.ts",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_test_path(path))


if __name__ == "__main__":
    unittest.main()
