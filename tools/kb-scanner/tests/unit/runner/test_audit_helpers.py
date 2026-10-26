"""用伪扫描和时钟验证离线审校工具，仅使用仓库夹具路径。"""
from contextlib import ExitStack
import itertools
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from kb_scanner.core import AnalysisSnapshot, StageResult
from kb_scanner.analyzers.architecture_family import ArchitectureFamilyAnalyzer
from tests import architecture_family_performance as family
from tests import cmake_report_audit as audit


class AuditHelperTests(unittest.TestCase):
    def test_family_measurement_and_entrypoint_use_local_cases_and_reject_failures(self):
        for mode in ("normal", "entry", "failed-scan", "changed-report", "slow-family"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
                output = Path(raw)
                ticks = itertools.count()
                stack.enter_context(patch("time.perf_counter", side_effect=lambda: next(ticks) * (2 if mode == "slow-family" else .001)))
                for method in ("start", "stop"):
                    stack.enter_context(patch("tracemalloc." + method))
                stack.enter_context(patch("tracemalloc.get_traced_memory", return_value=(0, 1024)))
                stack.enter_context(patch.object(ArchitectureFamilyAnalyzer, "analyze", return_value=StageResult(AnalysisSnapshot())))
                fake_sources = lambda *paths: paths
                fake_discover = lambda entities, budget: {"bucketOperations": len(entities), "familyCount": len(entities)//2}
                for target in ("tests.unit.test_architecture_family.sources", "tests.architecture_family_performance.sources"):
                    stack.enter_context(patch(target, side_effect=fake_sources))
                for target in ("kb_scanner.analyzers.architecture_family.grouping.discover", "tests.architecture_family_performance.discover"):
                    stack.enter_context(patch(target, side_effect=fake_discover))
                seen = []
                def scan(request):
                    seen.append(request.input_path)
                    ArchitectureFamilyAnalyzer().analyze(None, None, None, AnalysisSnapshot())
                    destination = Path(request.output_path)
                    destination.mkdir(parents=True, exist_ok=True)
                    payload = {"extensions": {family.NAMESPACE: {"familyCount": 2}}, "findings": [
                        {"fact": {"extensions": {family.NAMESPACE: {}}}},
                        {"fact": {"extensions": {family.NAMESPACE: {}, "kept": {}}}}]}
                    if mode == "changed-report" and destination.name.endswith("family"):
                        payload["unexpected"] = True
                    (destination/"scan-result.json").write_text(json.dumps(payload))
                    return SimpleNamespace(exit_code=1 if mode == "failed-scan" else 0, diagnostics=())
                app = SimpleNamespace(run=scan)
                for target in ("kb_scanner.pipeline.default.create_default_application", "tests.architecture_family_performance.create_default_application"):
                    stack.enter_context(patch(target, return_value=app))
                if mode == "entry":
                    stack.enter_context(patch("sys.argv", ["measure", "--output", raw]))
                    runpy.run_module("tests.architecture_family_performance", run_name="__main__")
                    result = json.loads((output/"performance.json").read_text())
                elif mode == "normal":
                    result = family.measure(output)
                else:
                    with self.assertRaises(AssertionError):
                        family.measure(output)
                    continue
                self.assertEqual([10000, 20000], [item["paths"] for item in result["synthetic"]])
                self.assertEqual(["demo", "family-demo"], [item["project"] for item in result["projects"]])
                self.assertEqual(4, len(seen))
                self.assertTrue(all(Path(path).is_relative_to(family.ROOT/"tests/fixtures") for path in seen))

    def test_report_audit_runs_both_versions_and_local_matrix_without_changing_oracles(self):
        for mode in ("run", "matrix", "entry-run", "entry-matrix", "failed-scan"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw, ExitStack() as stack:
                output = Path(raw)
                def cli(args):
                    target = Path(args[args.index("--output")+1])
                    target.mkdir(parents=True, exist_ok=True)
                    (target/"scan-result.json").write_text(json.dumps({"findings": [{"conclusion": {"suggestion":"中文", "suggestion_en":"English"}}]}))
                    (target/"scan.log").write_text("static")
                    return 1 if mode == "failed-scan" else 0
                stack.enter_context(patch.object(audit, "main", side_effect=cli))
                stack.enter_context(patch("kb_scanner.cli.main", side_effect=cli))
                scan = stack.enter_context(patch("tests.test_compatible_cutover_differential.run", return_value=(SimpleNamespace(exit_code=0), {"finding":"sample"})))
                stack.enter_context(patch("tests.test_compatible_cutover_differential.semantic_signature", side_effect=lambda payload,result,fixture: {"fixture":str(fixture)}))
                stack.enter_context(patch("kb_scanner.pipeline.default.create_default_application"))
                if mode.startswith("entry"):
                    stack.enter_context(patch("sys.argv", ["audit", raw] + (["--matrix"] if mode.endswith("matrix") else [])))
                    runpy.run_module("tests.cmake_report_audit", run_name="__main__")
                elif mode == "matrix":
                    audit.matrix(output)
                elif mode == "failed-scan":
                    with self.assertRaisesRegex(RuntimeError, "scan failed"):
                        audit.run(output)
                    continue
                else:
                    audit.run(output)
                if mode.endswith("matrix"):
                    signatures = json.loads((output/"candidate-signatures.json").read_text())
                    self.assertEqual(5, len(signatures))
                    self.assertEqual(5, scan.call_count)
                    self.assertTrue(all(Path(item["fixture"]).is_relative_to(audit.ROOT/"tests/fixtures") for item in signatures.values()))
                else:
                    result = json.loads((output/"candidate-hashes.json").read_text())
                    self.assertEqual(set(audit.CASES), set(result["fixtures"]))
                    self.assertEqual({"1.0", "2.0"}, set(result["after"]))
                    self.assertIsNotNone(result["fixtures"][audit.CASES[0]]["2.0"]["strippedSha256"])
