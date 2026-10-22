from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.frontend_coverage import evaluate_frontend_coverage


ROOT = Path(__file__).resolve().parents[1]


class FrontendTestInventoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = json.loads(
            (ROOT / "tests" / "frontend-test-inventory.json").read_text(encoding="utf-8")
        )

    def test_inventory_maps_every_business_module_both_ways(self) -> None:
        production = {
            path.name
            for path in (ROOT / "kb_scanner" / "frontends" / "cpp").glob("*.py")
            if path.name != "__init__.py"
        }
        mapped = set(self.inventory["modules"])
        self.assertEqual(production, mapped)
        self.assertEqual(len(mapped), 15)  # 宏事件、测试结构和有界标准 assert profile。
        for details in self.inventory["modules"].values():
            self.assertTrue((ROOT / details["unit"]).is_file())
            self.assertTrue(details["higherLayers"])
            for path in details["higherLayers"]:
                self.assertTrue((ROOT / path).is_file(), path)

    def test_recorded_frontend_classification_sums_to_38(self) -> None:
        baseline = self.inventory["baseline"]
        self.assertEqual(sum(baseline["classification"].values()), baseline["frontendAddedTests"])
        self.assertEqual(baseline["fullRegressionTests"], 126)


class CoverageGateSelfTests(unittest.TestCase):
    def payload(self, line_percent: float = 95.0, branch_percent: float = 85.0, executed: int = 1):
        statements = 1000
        branches = 1000
        return {
            "totals": {
                "num_statements": statements,
                "covered_lines": int(line_percent * 10),
                "num_branches": branches,
                "covered_branches": int(branch_percent * 10),
            },
            "files": {
                "kb_scanner/frontends/cpp/vocabulary.py": {
                    "summary": {"num_statements": 1, "covered_lines": executed}
                }
            },
        }

    def test_gate_accepts_thresholds_and_module_execution(self) -> None:
        result = evaluate_frontend_coverage(
            self.payload(), ("kb_scanner/frontends/cpp/vocabulary.py",),
            line_threshold=90.0, branch_threshold=80.0,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.failures, ())

    def test_gate_rejects_line_branch_and_missing_module_independently(self) -> None:
        line = evaluate_frontend_coverage(
            self.payload(line_percent=89.9), ("kb_scanner/frontends/cpp/vocabulary.py",),
            line_threshold=90.0, branch_threshold=80.0,
        )
        branch = evaluate_frontend_coverage(
            self.payload(branch_percent=79.9), ("kb_scanner/frontends/cpp/vocabulary.py",),
            line_threshold=90.0, branch_threshold=80.0,
        )
        missing = evaluate_frontend_coverage(
            self.payload(), ("kb_scanner/frontends/cpp/workspace.py",),
            line_threshold=90.0, branch_threshold=80.0,
        )
        self.assertTrue(any("line" in item for item in line.failures))
        self.assertTrue(any("branch" in item for item in branch.failures))
        self.assertTrue(any("workspace.py" in item for item in missing.failures))

    def test_gate_rejects_module_with_no_executed_lines(self) -> None:
        result = evaluate_frontend_coverage(
            self.payload(executed=0), ("kb_scanner/frontends/cpp/vocabulary.py",),
            line_threshold=90.0, branch_threshold=80.0,
        )
        self.assertFalse(result.passed)

    def test_gate_can_enforce_each_module_threshold(self) -> None:
        payload = self.payload()
        payload["files"]["kb_scanner/frontends/cpp/vocabulary.py"]["summary"] |= {
            "num_statements": 10,
            "covered_lines": 8,
            "num_branches": 10,
            "covered_branches": 7,
        }
        result = evaluate_frontend_coverage(
            payload, ("kb_scanner/frontends/cpp/vocabulary.py",),
            line_threshold=90.0, branch_threshold=80.0, enforce_module_thresholds=True,
        )
        self.assertTrue(any("vocabulary.py line" in item for item in result.failures))
        self.assertTrue(any("vocabulary.py branch" in item for item in result.failures))

    def test_test_runner_and_compose_keep_all_outputs_inside_container_tmp(self) -> None:
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        compose = (ROOT / "compose.test.yml").read_text(encoding="utf-8")
        runtime_lock = (ROOT / "requirements" / "runtime.lock").read_text(encoding="utf-8")
        test_lock = (ROOT / "requirements" / "test.lock").read_text(encoding="utf-8")
        self.assertIn('Path("/tmp/kb-scanner-frontend-unit.coverage")', runner)
        self.assertIn('Path("/tmp/kb-scanner-frontend-unit-coverage.json")', runner)
        self.assertEqual(compose.count("  kb-scanner-test:"), 1)
        self.assertIn("network_mode: none", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("/tmp:size=512m", compose)
        self.assertIn("coverage==7.10.6", test_lock)
        self.assertNotIn("coverage==", runtime_lock)


if __name__ == "__main__":
    unittest.main()
