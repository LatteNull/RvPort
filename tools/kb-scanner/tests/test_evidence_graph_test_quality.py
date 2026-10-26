from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EvidenceGraphTestQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = json.loads((ROOT / "tests" / "evidence-graph-test-inventory.json").read_text(encoding="utf-8"))

    def test_inventory_maps_graph_business_modules_and_higher_layers(self) -> None:
        expected = {"core/paths.py", "graph/store.py", "analyzers/proof.py", "analyzers/evidence_graph.py"}
        self.assertEqual(set(self.inventory["modules"]), expected)
        self.assertEqual(self.inventory["coverageThresholds"], {"linePercent": 90.0, "branchPercent": 90.0})
        for module, details in self.inventory["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / details["unit"]).is_file(), details["unit"])
            for higher in details["higherLayers"]:
                self.assertTrue((ROOT / higher).is_file(), higher)

    def test_runner_has_separate_graph_gate_and_tmp_outputs(self) -> None:
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn("--graph-unit", runner)
        self.assertIn('Path("/tmp/kb-scanner-evidence-graph-unit.coverage")', runner)
        self.assertIn('Path("/tmp/kb-scanner-evidence-graph-unit-coverage.json")', runner)
        self.assertIn("enforce_module_thresholds=True", runner)


if __name__ == "__main__":
    unittest.main()
