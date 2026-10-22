from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from tests.tree_sitter_native_support import (
    inspect_runtime,
    load_project_fixtures,
    run_scanner_process,
    runtime_payload,
    validate_runtime,
)
from tests.unit.frontends.cpp.support import make_context


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "tree-sitter-native-crash"
ARTIFACTS = {"scan-result.json", "scan-report.html", "scan.log"}


class TreeSitterNativeCrashRegressionTests(unittest.TestCase):
    def test_inventory_maps_modules_units_container_and_coverage_gates(self) -> None:
        inventory = json.loads(
            (ROOT / "tests" / "tree-sitter-native-crash-test-inventory.json").read_text(encoding="utf-8")
        )
        self.assertEqual("kb-scanner-test", inventory["container"])
        self.assertEqual({90.0, 80.0}, set(inventory["coverageThresholds"].values()))
        for module, mapping in inventory["modules"].items():
            self.assertTrue((ROOT / module).is_file(), module)
            self.assertTrue((ROOT / mapping["unit"]).is_file(), module)
            self.assertIn(mapping["coverageGate"], {"--frontend-unit", "--tree-sitter-native-crash-unit"})
        runner = (ROOT / "tests" / "run_container_tests.py").read_text(encoding="utf-8")
        self.assertIn("--tree-sitter-native-crash-unit", runner)
        self.assertIn('Path("/tmp/kb-scanner-tree-sitter-native-crash-unit.coverage")', runner)

    def test_production_adapter_contains_no_point_or_whole_tree_node_snapshot(self) -> None:
        adapter = (ROOT / "kb_scanner" / "frontends" / "cpp" / "tree_sitter_adapter.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("start_point", adapter)
        self.assertNotIn("end_point", adapter)
        self.assertNotIn("tuple(_walk", adapter)

    def test_locked_runtime_abi_is_compatible(self) -> None:
        runtime = inspect_runtime()
        print("tree-sitter-runtime=" + json.dumps(runtime_payload(runtime), sort_keys=True), flush=True)
        self.assertEqual((), validate_runtime(runtime))

    def test_reduced_upstream_triggers_have_no_unbound_selection_evidence(self) -> None:
        for fixture in load_project_fixtures(FIXTURE_ROOT):
            project_root = FIXTURE_ROOT / fixture.project_id
            relative = fixture.fixture_path.relative_to(project_root).as_posix()
            entity = make_source_file_entity(relative, ("c", "cpp"), "1")
            result = TreeSitterCppAdapter().analyze_file(make_context(project_root), project_root, relative, entity)
            self.assertIsNotNone(result.value, fixture.project_id)
            repeated = TreeSitterCppAdapter().analyze_file(make_context(project_root), project_root, relative, entity)
            self.assertIsNotNone(repeated.value, fixture.project_id)
            self.assertEqual(
                [item.id for item in result.value],
                [item.id for item in repeated.value],
                fixture.project_id,
            )
            self.assertLessEqual(len(result.value), fixture.max_frontend_evidence, fixture.project_id)
            self.assertFalse(
                any(item.kind in {"selection_condition", "constexpr_condition"} for item in result.value),
                fixture.project_id,
            )

    def test_three_pinned_projects_exit_normally_with_v2_and_v1_artifacts(self) -> None:
        for fixture in load_project_fixtures(FIXTURE_ROOT):
            project_root = FIXTURE_ROOT / fixture.project_id
            for schema_version, expected_schema in ((None, "2.0"), ("1.0", "1.0")):
                with self.subTest(project=fixture.project_id, schema=expected_schema), tempfile.TemporaryDirectory(
                    prefix=f"kb-native-{fixture.project_id}-{expected_schema}-"
                ) as raw_output:
                    output = Path(raw_output)
                    outcome = run_scanner_process(
                        project_root,
                        RULES,
                        output,
                        schema_version=schema_version,
                        timeout_seconds=fixture.max_duration_seconds,
                    )
                    self.assertEqual("normal", outcome.status, outcome)
                    self.assertEqual(0, outcome.returncode)
                    self.assertLess(outcome.duration_seconds, fixture.max_duration_seconds)
                    self.assertEqual(ARTIFACTS, {item.name for item in output.iterdir()})
                    payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))
                    self.assertEqual(expected_schema, payload["schemaVersion"])
                    tool = payload["scan"]["tool"] if expected_schema == "2.0" else payload["tool"]
                    self.assertEqual("kb-scanner", tool["name"])


if __name__ == "__main__":
    unittest.main()
