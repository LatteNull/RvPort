from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeDetectionTestQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = json.loads((ROOT / "tests" / "knowledge-detection-test-inventory.json").read_text(encoding="utf-8"))

    def test_inventory_maps_all_new_or_modified_business_modules(self) -> None:
        expected = {
            "core/knowledge.py", "core/facts.py", "core/results.py", "core/observations.py", "core/protocols.py",
            "knowledge/schema.py", "knowledge/identity.py", "knowledge/provider.py", "normalization/cpp.py",
            "detectors/definitions.py", "detectors/matchers.py", "detectors/local.py", "pipeline/qualification.py",
        }
        self.assertEqual(set(self.inventory["modules"]), expected)
        for module, details in self.inventory["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / details["unit"]).is_file(), details["unit"])
            self.assertTrue(details["higherLayers"])
            for path in details["higherLayers"]:
                self.assertTrue((ROOT / path).is_file(), path)

    def test_inventory_and_runner_preserve_layering_and_tmp_outputs(self) -> None:
        self.assertEqual(self.inventory["baseline"], {"frontendUnitTests": 41, "fullRegressionTests": 126})
        self.assertEqual(self.inventory["coverageThresholds"], {"linePercent": 90.0, "branchPercent": 80.0})
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertLess(runner.index("_knowledge_detection_unit_gate()"), runner.index("_unit_gate()", runner.index("def main")))
        self.assertIn('Path("/tmp/kb-scanner-knowledge-detection-unit.coverage")', runner)
        self.assertIn('Path("/tmp/kb-scanner-knowledge-detection-unit-coverage.json")', runner)
        self.assertIn("enforce_module_thresholds=True", runner)


if __name__ == "__main__":
    unittest.main()
