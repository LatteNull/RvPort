"""使用伪覆盖率报告和进程边界验证测试编排。"""

from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests import run_container_tests as runner
from tests.unit.runner.test_mapping import example_case


MAPPED_GATES = (
    "_unit_gate", "_knowledge_detection_unit_gate", "_knowledge_production_unit_gate",
    "_evidence_graph_unit_gate", "_build_selection_unit_gate", "_classification_assessment_unit_gate",
    "_compatible_cutover_unit_gate", "_projection_reachability_unit_gate",
    "_schema_v2_projection_unit_gate", "_architecture_enum_unit_gate",
)


@contextmanager
def environment(*, report_ok=True, tests_ok=True, exists=True, performance=False,
                empty=False, native_errors=()):
    mapping = {"unit": "tests/unit/example.py", "supportingUnits": []}
    inventory = {"coverageThresholds": {"linePercent": 90, "branchPercent": 90},
                 "modules": {"example.py": ["tests.unit.example"] if performance else mapping},
                 "productionModules": []}
    summary = {"covered_lines": 0 if empty or not report_ok else 10,
               "num_statements": 0 if empty else 10,
               "covered_branches": 0 if empty or not report_ok else 10,
               "num_branches": 0 if empty else 10}
    payload = {"totals": summary, "files": {name: {"summary": summary,
                "missing_lines": [], "missing_branches": []} for name in (
                "example.py", "kb_scanner/example.py", "kb_scanner/frontends/cpp/example.py",
                "tests/tree_sitter_native_support.py", "tests/unit_mapping.py", "tests/run_container_tests.py",
                "tests/architecture_family_performance.py", "tests/cmake_report_audit.py")}}
    fake_coverage = Mock()
    result = Mock()
    result.wasSuccessful.return_value = tests_ok

    def read(path, *args, **kwargs):
        return json.dumps(inventory if "inventory" in path.name else payload)

    def discovered(*args, **kwargs):
        return unittest.TestSuite([unittest.TestSuite([
            example_case("unit.accepted", []),
            example_case("unit.ArchitectureEnumFrontendTests.component", []),
        ])])

    with ExitStack() as stack:
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(redirect_stderr(io.StringIO()))
        stack.enter_context(patch.object(Path, "read_text", autospec=True, side_effect=read))
        stack.enter_context(patch.object(Path, "is_file", return_value=exists))
        stack.enter_context(patch.object(runner, "Coverage", return_value=fake_coverage))
        run = stack.enter_context(patch.object(runner, "_run", return_value=result))
        mapped = stack.enter_context(patch.object(runner, "mapped_suite", side_effect=discovered))
        stack.enter_context(patch.object(unittest.defaultTestLoader, "discover", side_effect=discovered))
        stack.enter_context(patch.object(unittest.defaultTestLoader, "loadTestsFromName", side_effect=discovered))
        from tests import tree_sitter_native_support as native
        stack.enter_context(patch.object(native, "inspect_runtime", return_value=object()))
        stack.enter_context(patch.object(native, "runtime_payload", return_value={}))
        stack.enter_context(patch.object(native, "validate_runtime", return_value=list(native_errors)))
        yield SimpleNamespace(coverage=fake_coverage, run=run, mapped=mapped, inventory=inventory)


class RunnerTests(unittest.TestCase):
    def test_runner_gate_checks_its_own_modules_and_propagates_failures(self):
        for report_ok, tests_ok in ((True, True), (False, True), (True, False)):
            with environment(report_ok=report_ok, tests_ok=tests_ok) as fake:
                self.assertEqual(report_ok and tests_ok, runner._runner_unit_gate())
                fake.coverage.json_report.assert_called_once_with(outfile="/tmp/kb-runner-coverage.json")

    def test_mapped_gates_require_successful_tests_and_coverage(self):
        for name in MAPPED_GATES:
            for report_ok, tests_ok in ((True, True), (False, True), (True, False)):
                with self.subTest(name=name, report_ok=report_ok, tests_ok=tests_ok):
                    with environment(report_ok=report_ok, tests_ok=tests_ok) as fake:
                        self.assertEqual(report_ok and tests_ok, getattr(runner, name)())
                        fake.mapped.assert_called_once()
                        fake.coverage.start.assert_called_once()
                        fake.coverage.stop.assert_called_once()
                        fake.coverage.json_report.assert_called_once()
                        self.assertEqual(1, fake.run.call_count)

    def test_zero_statement_or_branch_reports_do_not_crash(self):
        for name in MAPPED_GATES:
            with self.subTest(name=name), environment(empty=True):
                self.assertFalse(getattr(runner, name)())

    def test_mapped_suite_load_error_propagates(self):
        for name in MAPPED_GATES:
            with self.subTest(name=name), environment() as fake:
                fake.mapped.side_effect = ValueError("broken mapping")
                with self.assertRaisesRegex(ValueError, "broken mapping"):
                    getattr(runner, name)()
                fake.run.assert_not_called()

    def test_missing_declared_units_fail_before_test_execution(self):
        for name in ("_schema_v2_projection_unit_gate", "_architecture_enum_unit_gate",
                     "_tree_sitter_native_crash_unit_gate", "_architecture_candidate_noise_unit_gate"):
            with self.subTest(name=name), environment(exists=False) as fake:
                self.assertFalse(getattr(runner, name)())
                fake.run.assert_not_called()
        with environment(exists=False, performance=True):
            with self.assertRaisesRegex(ValueError, "missing performance unit"):
                runner._performance_unit_gate()

    def test_native_runtime_gate_and_schema_contract_reject_invalid_inputs(self):
        with environment(native_errors=("bad native library",)) as fake:
            self.assertFalse(runner._tree_sitter_native_crash_unit_gate())
            fake.coverage.json_report.assert_not_called()
        for report_ok in (True, False):
            with environment(report_ok=report_ok):
                self.assertEqual(report_ok, runner._tree_sitter_native_crash_unit_gate())
        with environment() as fake:
            self.assertTrue(runner._schema_v2_contract_gate())
            fake.inventory["productionModules"] = ["unexpected.py"]
            self.assertFalse(runner._schema_v2_contract_gate())

    def test_isolated_candidate_and_performance_gates_filter_non_unit_cases(self):
        for report_ok in (True, False):
            for label in ("candidate-noise", "rpm-architecture"):
                with self.subTest(label=label), environment(report_ok=report_ok) as fake:
                    self.assertEqual(report_ok, runner._architecture_candidate_noise_unit_gate(label=label))
                    selected = list(fake.run.call_args.args[0])
                    self.assertEqual(["unit.accepted"], [case.id() for case in selected])
            with environment(report_ok=report_ok, performance=True) as fake:
                self.assertEqual(report_ok, runner._performance_unit_gate())
                self.assertEqual(1, fake.run.call_args.args[0].countTestCases())

    def test_full_regression_and_output_runner_return_actual_test_result(self):
        with environment() as fake, patch.object(Path, "glob", return_value=[Path("test_one.py")]):
            self.assertTrue(runner._full_regression())
            self.assertEqual("full-regression", fake.run.call_args.args[1])
        result = unittest.TestResult()
        with patch.object(unittest, "TextTestRunner") as text_runner, redirect_stdout(io.StringIO()):
            text_runner.return_value.run.return_value = result
            suite = unittest.TestSuite()
            self.assertIs(result, runner._run(suite, "fixture"))
            text_runner.return_value.run.assert_called_once_with(suite)

    def test_modes_and_default_sequence_propagate_failures(self):
        modes = {
            "--runner-unit": "_runner_unit_gate",
            "--regression-only": "_full_regression", "--knowledge-unit": "_knowledge_detection_unit_gate",
            "--knowledge-production-unit": "_knowledge_production_unit_gate", "--frontend-unit": "_unit_gate",
            "--graph-unit": "_evidence_graph_unit_gate", "--build-selection-unit": "_build_selection_unit_gate",
            "--classification-assessment-unit": "_classification_assessment_unit_gate",
            "--compatible-cutover-unit": "_compatible_cutover_unit_gate",
            "--projection-reachability-unit": "_projection_reachability_unit_gate",
            "--schema-v2-contract": "_schema_v2_contract_gate",
            "--schema-v2-projection-unit": "_schema_v2_projection_unit_gate",
            "--architecture-enum-unit": "_architecture_enum_unit_gate",
            "--tree-sitter-native-crash-unit": "_tree_sitter_native_crash_unit_gate",
            "--rpm-architecture-unit": "_architecture_candidate_noise_unit_gate",
            "--candidate-semantic-admission-unit": "_architecture_candidate_noise_unit_gate",
            "--architecture-candidate-noise-unit": "_architecture_candidate_noise_unit_gate",
            "--performance-unit": "_performance_unit_gate",
        }
        for mode, name in modes.items():
            for passed in (True, False):
                with self.subTest(mode=mode, passed=passed), patch.object(runner.sys, "argv", ["runner", mode]), patch.object(runner, name, return_value=passed) as gate:
                    self.assertEqual(0 if passed else 1, runner.main())
                    gate.assert_called_once()
        with patch.object(runner.sys, "argv", ["runner", "--source-evidence-chain-unit"]), patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=7)):
            self.assertEqual(7, runner.main())
        for code in (0, 7):
            with patch.object(runner.sys, "argv", ["runner"]), patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=code)) as child, patch.object(runner, "_full_regression", return_value=True) as regression:
                self.assertEqual(code, runner.main())
                if code:
                    self.assertEqual(1, child.call_count)
                    regression.assert_not_called()
                else:
                    self.assertEqual(18, child.call_count)
                    self.assertEqual(18, len({call.args[0][-1] for call in child.call_args_list}))
                    regression.assert_called_once()
