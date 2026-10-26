from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClassificationAssessmentContractTests(unittest.TestCase):
    def test_inventory_maps_every_business_module_to_real_unit_and_higher_layer_tests(self) -> None:
        payload = json.loads((ROOT / "tests/classification-assessment-test-inventory.json").read_text(encoding="utf-8"))
        expected = {
            "frontends/build/adapters.py", "normalization/build.py",
            "core/classifications.py", "core/test_vocabulary.py", "core/observations.py", "core/results.py",
            "analyzers/test_selection.py", "detectors/test_selection.py", "classifiers/policy.py",
            "classifiers/migration.py", "assessors/vocabulary.py", "assessors/migration.py",
            "pipeline/composite.py", "pipeline/qualification.py",
        }
        self.assertEqual(set(payload["modules"]), expected)
        self.assertEqual(payload["coverageThresholds"], {"linePercent": 90.0, "branchPercent": 90.0})
        for module, mapping in payload["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / mapping["unit"]).is_file(), mapping["unit"])
            self.assertTrue(mapping["higherLayers"])
            self.assertTrue(all((ROOT / path).is_file() for path in mapping["higherLayers"]))

    def test_modules_do_not_import_legacy_or_execution_and_network_runtimes(self) -> None:
        payload = json.loads((ROOT / "tests/classification-assessment-test-inventory.json").read_text(encoding="utf-8"))
        forbidden = {"subprocess", "socket", "requests", "urllib", "kb_scanner.adapters.legacy", "kb_scanner.compile_commands", "kb_scanner.models", "kb_scanner.rules", "kb_scanner.report"}
        for module in payload["modules"]:
            path = ROOT / "kb_scanner" / module
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
            self.assertFalse(any(any(name == item or name.startswith(item + ".") for item in forbidden) for name in imports), module)

    def test_container_and_documented_scope_remain_strict(self) -> None:
        compose = (ROOT / "compose.test.yml").read_text(encoding="utf-8")
        self.assertIn("network_mode: none", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop:", compose)
        self.assertNotIn("../docker-compose", compose)
        design = (ROOT / "docs/classification-assessment-design.md").read_text(encoding="utf-8")
        for value in ("staticScopeOnly=true", "compiled=false", "testsExecuted=false", "schema 1.0", "Legacy"):
            self.assertIn(value, design)
        runner = (ROOT / "tests/run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn("--classification-assessment-unit", runner)


if __name__ == "__main__":
    unittest.main()
