from __future__ import annotations

import json
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "tests" / "fixtures" / "evidence-graph" / "avx-manual-baseline.json"


class AvxManualBaselineTests(unittest.TestCase):
    def test_baseline_is_audited_versioned_and_has_expected_counts(self) -> None:
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertRegex(payload["fixture"]["revision"], r"^[0-9a-f]{40}$")
        self.assertIn("Manual source review", payload["fixture"]["audit"])
        self.assertFalse(payload["legacyOracle"])
        self.assertEqual(
            payload["auditedCounts"],
            {
                "x86Headers": 39,
                "x86VectorTypes": 362,
                "directIntrinsicCalls": 360,
                "commentHints": 45,
                "functionLikeMacroDefinitions": 12,
                "replacementTerminalIntrinsicReferences": 18,
            },
        )

    def test_paths_spans_and_entries_are_unique_and_bounded(self) -> None:
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        files = payload["sourceFiles"]
        self.assertEqual(len(files), 37)
        self.assertEqual(len(files), len(set(files)))
        for path in files:
            parsed = PurePosixPath(path)
            self.assertFalse(parsed.is_absolute())
            self.assertNotIn("..", parsed.parts)
            self.assertIn(parsed.suffix, {".c", ".h"})

        definitions = payload["macroDefinitions"]
        keys = {(item["path"], item["name"], tuple(item["definition"]["start"])) for item in definitions}
        self.assertEqual(len(definitions), 12)
        self.assertEqual(len(keys), len(definitions))
        calls = [call for item in definitions for call in item["replacementCalls"]]
        self.assertEqual(len(calls), 18)
        for item in definitions:
            self.assertIn(item["path"], files)
            self._assert_span(item["definition"])
            for call in item["replacementCalls"]:
                self.assertTrue(call["name"].startswith("_mm"))
                self._assert_span(call["span"])

    def test_build_facts_are_formally_covered_and_manual_corrections_are_recorded(self) -> None:
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        build = payload["buildEvidence"]
        self.assertEqual(build["status"], "implemented-build-selection")
        self.assertEqual((build["makefiles"], build["x86FlagOccurrences"]), (4, 24))
        self.assertEqual(build["baseline"], "tests/fixtures/build-selection/avx-make-baseline.json")
        self.assertEqual(payload["baselineCorrections"][0]["entries"], 3)
        self.assertIn("scanner output was already correct", payload["baselineCorrections"][0]["reason"])

    def _assert_span(self, span: dict[str, list[int]]) -> None:
        start = tuple(span["start"])
        end = tuple(span["end"])
        self.assertEqual((len(start), len(end)), (2, 2))
        self.assertGreaterEqual(start[0], 1)
        self.assertGreaterEqual(start[1], 1)
        self.assertGreater(end, start)


if __name__ == "__main__":
    unittest.main()
