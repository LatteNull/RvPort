from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeProductionTestQualityTests(unittest.TestCase):
    def test_inventory_maps_each_new_business_module_to_isolated_and_higher_tests(self) -> None:
        inventory = json.loads((ROOT / "tests" / "knowledge-production-test-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(set(inventory["modules"]), {"knowledge/production.py", "knowledge/extractors.py"})
        self.assertEqual(inventory["coverageThresholds"], {"linePercent": 90.0, "branchPercent": 90.0})
        for module, details in inventory["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file())
            self.assertTrue((ROOT / details["unit"]).is_file())
            self.assertTrue(all((ROOT / path).is_file() for path in details["higherLayers"]))

    def test_runner_has_separate_production_gate_and_tmp_outputs(self) -> None:
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn('"--knowledge-production-unit"', runner)
        self.assertIn('Path("/tmp/kb-scanner-knowledge-production-unit.coverage")', runner)
        self.assertIn('Path("/tmp/kb-scanner-knowledge-production-unit-coverage.json")', runner)
        main = runner[runner.index("def main") :]
        self.assertLess(main.index("--knowledge-production-unit"), main.index("--knowledge-unit"))

    def test_extractor_boundary_has_no_network_subprocess_or_upstream_writes(self) -> None:
        extractor = (ROOT / "kb_scanner" / "knowledge" / "extractors.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "requests", "urllib", ".write_text(", ".write_bytes(", "git clone"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, extractor)
        compose = (ROOT / "compose.test.yml").read_text(encoding="utf-8")
        self.assertEqual(compose.count("  kb-scanner-test:"), 1)
        self.assertIn("network_mode: none", compose)


if __name__ == "__main__":
    unittest.main()
