from __future__ import annotations

import ast
import json
from importlib.util import resolve_name
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildSelectionContractTests(unittest.TestCase):
    def test_inventory_maps_every_formal_module_and_test_layer(self) -> None:
        payload = json.loads((ROOT / "tests" / "build-selection-test-inventory.json").read_text(encoding="utf-8"))
        expected = {
            'frontends/build/rpm/macros.py', 'frontends/build/rpm/conditions.py', 'frontends/build/rpm/records.py',
            'frontends/build/rpm/dependencies.py', 'frontends/build/rpm/parser.py', 'frontends/build/rpm/shell.py',
            'analyzers/rpm_selection.py',
            "frontends/build/vocabulary.py", "frontends/build/safety.py", "frontends/build/workspace.py",
            "frontends/build/make.py", "frontends/build/adapters.py", "frontends/build/frontend.py",
            "normalization/build.py", "analyzers/build_selection.py", "detectors/build_selection.py", "pipeline/composite.py",
        }
        self.assertEqual(set(payload["modules"]), expected)
        self.assertEqual(payload["coverageThresholds"], {"linePercent": 90.0, "branchPercent": 90.0})
        for module, mapping in payload["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / mapping["unit"]).is_file(), mapping["unit"])
            self.assertTrue(mapping["higherLayers"])
            self.assertTrue(all((ROOT / path).is_file() for path in mapping["higherLayers"]))

    def test_formal_modules_do_not_import_legacy_or_execution_runtime(self) -> None:
        inventory = json.loads((ROOT / "tests" / "build-selection-test-inventory.json").read_text(encoding="utf-8"))
        forbidden = {"subprocess", "os.system", "kb_scanner.adapters.legacy", "kb_scanner.compile_commands", "kb_scanner.cpp_frontend", "kb_scanner.models", "kb_scanner.rules", "kb_scanner.report", "rpm", "specfile"}
        for module in inventory["modules"]:
            path = ROOT / "kb_scanner" / module
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    package = 'kb_scanner.' + module.removesuffix('.py').replace('/', '.').rpartition('.')[0]
                    imports.add(resolve_name('.' * node.level + node.module, package))
            for name in imports:
                self.assertFalse(any(name == item or name.startswith(item + ".") for item in forbidden), (module, name))

    def test_support_matrix_and_runner_keep_static_container_boundary(self) -> None:
        matrix = (ROOT / "docs" / "build-support.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("不执行项目命令", matrix)
        self.assertIn("不建模交叉编译误选", matrix)
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn("--build-selection-unit", runner)
        self.assertIn("/tmp/kb-scanner-build-selection-unit.coverage", runner)


if __name__ == "__main__":
    unittest.main()
