from __future__ import annotations

import json
import unittest

from tests.unit.classification_assessment.support import ROOT


class BaselineTests(unittest.TestCase):
    def test_behavior_matrix_has_unique_complete_cases_and_rejection_boundaries(self) -> None:
        payload = json.loads((ROOT / "tests/fixtures/classification-assessment/behavior-matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        ids = [item["id"] for item in payload["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            {item["observation"] for item in payload["cases"]},
            {"x86_test_guarded", "riscv_test_blocker", "riscv_test_coverage_gap", "test_selection_unknown"},
        )
        self.assertIn("name-similarity-proves-coverage", payload["rejectedInferences"])
        for item in payload["cases"]:
            if item["classification"] == "unknown":
                self.assertTrue(item.get("proof") == "unknown" or item.get("selection") == "unknown")

    def test_project_oracle_covers_every_state_and_readiness_veto(self) -> None:
        payload = json.loads((ROOT / "tests/fixtures/classification-assessment/project-state-oracle.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(payload["states"]),
            {"architecture_independent", "x86_only", "multiarch_without_riscv", "partial_riscv", "riscv_ready", "provisional", "unknown"},
        )
        self.assertEqual(set(payload["states"]["riscv_ready"]["veto"]), {"blocker", "unknown", "configuration-conflict"})
        for state in payload["states"].values():
            self.assertTrue(state["requires"])


if __name__ == "__main__":
    unittest.main()
