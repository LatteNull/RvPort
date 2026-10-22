from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectionReachabilityTestQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = json.loads(
            (ROOT / "tests" / "projection-reachability-test-inventory.json").read_text(encoding="utf-8")
        )

    def test_inventory_maps_every_changed_business_module_to_isolated_tests(self) -> None:
        expected = {
            "projection/reference.py",
            "analyzers/macro_resolution.py",
            "analyzers/relation_diagnostics.py",
            "analyzers/build_selection.py",
            "projection/mapper.py",
            "projection/diagnostics.py",
            "projection/renderers.py",
            "classifiers/policy.py",
            "classifiers/migration.py",
            "assessors/migration.py",
        }
        self.assertEqual(expected, set(self.inventory["modules"]))
        self.assertEqual({"linePercent": 90.0, "branchPercent": 80.0}, self.inventory["coverageThresholds"])
        self.assertEqual("kb-scanner-test", self.inventory["container"])
        for module, details in self.inventory["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / details["unit"]).is_file(), details["unit"])
            self.assertIn("tests/unit/", details["unit"])
            for unit in details.get("supportingUnits", ()):
                self.assertTrue((ROOT / unit).is_file(), unit)
                self.assertIn("tests/unit/", unit)
            for higher in details["higherLayers"]:
                self.assertTrue((ROOT / higher).is_file(), higher)

    def test_runner_has_separate_projection_reachability_gate_and_tmp_outputs(self) -> None:
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn("--projection-reachability-unit", runner)
        self.assertIn('Path("/tmp/kb-scanner-projection-reachability-unit.coverage")', runner)
        self.assertIn('Path("/tmp/kb-scanner-projection-reachability-unit-coverage.json")', runner)
        self.assertIn("enforce_module_thresholds=True", runner)


if __name__ == "__main__":
    unittest.main()
