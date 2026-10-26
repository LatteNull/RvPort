"""映射加载的行为测试，不启动分析器或外部进程。"""

import io
import sys
import tempfile
import types
import unittest
import tests.unit
from pathlib import Path
from unittest.mock import Mock, patch

from tests.unit_mapping import mapped_suite


def example_case(name, calls, fail=False):
    class Example(unittest.TestCase):
        def runTest(self):
            calls.append(name)
            self.assertFalse(fail, "fixture failure")

        def id(self):
            return name

    return Example()


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.unit = self.root / "tests/unit"
        self.unit.mkdir(parents=True)
        for name in ("test_main.py", "test_support.py", "test_extra.py"):
            (self.unit / name).write_text("", encoding="utf-8")
        self.inventory = {"modules": {"module.py": {
            "unit": "tests/unit/test_main.py",
            "supportingUnits": ["tests/unit/test_support.py"],
        }}}

    def loader(self, calls):
        loader = Mock(spec=unittest.TestLoader)
        loader.errors = []
        loader.loadTestsFromName.side_effect = lambda name: unittest.TestSuite([
            unittest.TestSuite([example_case(name, calls)])])
        return loader

    def test_supporting_extra_and_discovered_cases_run_once_in_stable_order(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                calls = []
                loader = self.loader(calls)
                loader.discover.return_value = unittest.TestSuite([
                    example_case("tests.unit.test_main", calls),
                    example_case("discovered", calls),
                ])
                entries = [("b.py", self.inventory["modules"]["module.py"]),
                           ("a.py", {"unit": "tests/unit/test_support.py"})]
                inventory = {"modules": dict(reversed(entries) if reverse else entries)}
                suite = mapped_suite(self.root, inventory, discover=self.unit,
                                     extra_units=("tests/unit/test_extra.py",), loader=loader)
                result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
                self.assertTrue(result.wasSuccessful())
                self.assertEqual(["discovered", "tests.unit.test_extra", "tests.unit.test_main",
                                  "tests.unit.test_support"], calls)
                loader.discover.assert_called_once_with(str(self.unit), pattern="test_*.py",
                                                        top_level_dir=str(self.root.resolve()))
                self.assertEqual(3, loader.loadTestsFromName.call_count)

    def test_invalid_inventory_and_mapping_shapes_fail(self):
        cases = ({}, {"modules": {}}, {"modules": []},
                 {"modules": {"x": None}}, {"modules": {"x": {}}},
                 {"modules": {"x": {"unit": "tests/unit/test_main.py", "supportingUnits": "bad"}}})
        for inventory in cases:
            with self.subTest(inventory=inventory), self.assertRaises(ValueError):
                mapped_suite(self.root, inventory)

    def test_missing_invalid_and_escaping_paths_fail_before_loading(self):
        (self.unit / "notes.txt").write_text("fixture")
        for path in (None, 4, "", "tests/unit/missing.py", "tests/unit/notes.txt",
                     "tests/unit", "tests/unit/../test_outside.py",
                     "tests/test_contract.py", str(self.unit / "test_main.py")):
            for supporting in (False, True):
                with self.subTest(path=path, supporting=supporting):
                    mapping = {"unit": "tests/unit/test_main.py", "supportingUnits": [path]} if supporting else {"unit": path}
                    loader = self.loader([])
                    with self.assertRaises(ValueError):
                        mapped_suite(self.root, {"modules": {"module.py": mapping}}, loader=loader)
                    loader.loadTestsFromName.assert_not_called()

    def test_symlink_outside_unit_root_is_rejected(self):
        outside = self.root / "outside.py"
        outside.write_text("fixture")
        link = self.unit / "escape.py"
        link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escape.py"):
            mapped_suite(self.root, {"modules": {"x": {"unit": "tests/unit/escape.py"}}})

    def test_empty_module_and_import_errors_are_not_silently_ignored(self):
        loader = self.loader([])
        loader.loadTestsFromName.side_effect = None
        loader.loadTestsFromName.return_value = unittest.TestSuite()
        with self.assertRaisesRegex(ValueError, "没有加载到测试"):
            mapped_suite(self.root, self.inventory, loader=loader)
        loader = self.loader([])
        loader.errors = ["missing dependency in tests.unit.test_support"]
        with self.assertRaisesRegex(ValueError, "missing dependency"):
            mapped_suite(self.root, self.inventory, loader=loader)

    def test_real_loader_preserves_test_failure(self):
        module = types.ModuleType("tests.unit.test_main")
        calls = []
        module.load_tests = lambda loader, tests, pattern: unittest.TestSuite([
            example_case("failure", calls, fail=True)])
        inventory = {"modules": {"x": {"unit": "tests/unit/test_main.py"}}}
        with patch.dict(sys.modules, {module.__name__: module}), patch.object(
                tests.unit, "test_main", module, create=True):
            suite = mapped_suite(self.root, inventory)
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        self.assertEqual(["failure"], calls)
        self.assertEqual(1, len(result.failures))

    def test_real_loader_rejects_failed_import(self):
        inventory = {"modules": {"x": {"unit": "tests/unit/test_main.py"}}}
        with self.assertRaisesRegex(ValueError, "test_main"):
            mapped_suite(self.root, inventory)
