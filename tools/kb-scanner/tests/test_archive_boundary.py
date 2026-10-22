from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "archive" / "2026-09-04-pre-rewrite"


class ArchiveBoundaryTests(unittest.TestCase):
    def test_retired_snapshot_is_not_shipped(self) -> None:
        self.assertFalse(SNAPSHOT.exists())

    def test_archive_is_outside_runtime_package_and_test_discovery_root(self) -> None:
        package_root = (ROOT / "kb_scanner").resolve()
        test_root = (ROOT / "tests").resolve()
        archive_root = SNAPSHOT.resolve()
        self.assertFalse(archive_root.is_relative_to(package_root))
        self.assertFalse(archive_root.is_relative_to(test_root))
        self.assertFalse(any(path.is_relative_to(archive_root) for path in package_root.rglob("*.py")))
        suite = unittest.defaultTestLoader.discover(str(test_root), pattern="test*.py")
        discovered_ids = [case.id() for group in suite for subgroup in group for case in subgroup]
        self.assertFalse(any(case_id.startswith("archive.") for case_id in discovered_ids))


if __name__ == "__main__":
    unittest.main()
