from __future__ import annotations

import json
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "tests" / "fixtures" / "build-selection" / "avx-make-baseline.json"


class BuildBaselineTests(unittest.TestCase):
    def test_avx_make_baseline_is_manual_versioned_unique_and_bounded(self) -> None:
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertRegex(payload["revision"], r"^[0-9a-f]{40}$")
        self.assertIn("Manual", payload["audit"])
        entries = payload["entries"]
        self.assertEqual(payload["expectedCount"], 24)
        self.assertEqual(len(entries), 24)
        keys = {(item["path"], item["line"], item["flag"]) for item in entries}
        self.assertEqual(len(keys), len(entries))
        self.assertEqual(len({item["path"] for item in entries}), 4)
        for item in entries:
            path = PurePosixPath(item["path"])
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertEqual(item["line"], 5)
            self.assertTrue(item["flag"].startswith("-m"))
            self.assertGreater(item["endColumn"], item["startColumn"])
            self.assertIn(item["expectedStatus"], {"selected", "inactive", "unknown"})
            if item["expectedStatus"] == "unknown":
                self.assertTrue(item["reason"])


if __name__ == "__main__":
    unittest.main()
