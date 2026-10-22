from __future__ import annotations

import unittest

from pathspec import GitIgnoreSpec


class SupportTechnologyTests(unittest.TestCase):
    def test_pathspec_can_represent_git_style_workspace_filters(self) -> None:
        spec = GitIgnoreSpec.from_lines(["build/", "vendor/**", "!vendor/portable/**"])

        self.assertTrue(spec.match_file("build/generated.c"))
        self.assertTrue(spec.match_file("vendor/x86/simd.c"))
        self.assertFalse(spec.match_file("vendor/portable/fallback.c"))
        self.assertFalse(spec.match_file("src/main.c"))


if __name__ == "__main__":
    unittest.main()
