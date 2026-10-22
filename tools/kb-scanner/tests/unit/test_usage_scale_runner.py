"""用途规模驱动的隔离测试：真实扫描、进程与渲染均替换为边界 fake。"""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import run_usage_scale_tests as runner
from tests.unit.test_usage_scale_acceptance import valid_pair


class UsageScaleRunnerTests(unittest.TestCase):
    def test_source_keeps_requested_density(self):
        sparse = runner.source(5000, "sparse")
        dense = runner.source(5000, "dense")
        self.assertEqual(sparse.count("void f"), 200)
        self.assertEqual(sparse.count("FORMAT_X86_"), 52)
        self.assertEqual(dense.count("FORMAT_LOCAL_"), 0)

    def _child(self, mode="enabled", *, roots=96, usage=True, findings=0, artifacts=True,
               chunks=False, cli_code=0):
        with TemporaryDirectory() as temporary, ExitStack() as guards:
            out = Path(temporary) / "result"
            args = SimpleNamespace(output=out, references=10000, density="sparse", mode=mode)
            report = SimpleNamespace(findings=[SimpleNamespace(fact=SimpleNamespace(extensions={
                runner.NAMESPACE: {"roots": [{"analysisTruncated": True}]}})) for _ in range(findings)],
                extensions={runner.NAMESPACE: {"statistics": {"rootCount": roots},
                    "excludedCount": roots - findings}} if usage else {})
            guards.enter_context(patch.object(runner, "render_json", return_value=b"{}"))
            guards.enter_context(patch.object(runner, "render_json_chunks", return_value=iter([b"{}"])))
            guards.enter_context(patch.object(runner.V2FindingMapper, "map", return_value=None))
            def fake_main(argv):
                destination = Path(argv[argv.index("--output") + 1])
                destination.mkdir()
                for name in ("scan-result.json", "scan-report.html", "scan.log") if artifacts else ("scan.log",):
                    (destination / name).write_text("fixture")
                from kb_scanner.projection.v2 import projector
                render = projector.render_json_chunks if chunks else projector.render_json
                render(report)
                runner.V2FindingMapper.map(None)
                return cli_code
            guards.enter_context(patch.object(runner, "main", side_effect=fake_main))
            guards.enter_context(patch("builtins.print"))
            code = runner.child(args)
            metrics = json.loads((out / "metrics.json").read_text())
            self.assertTrue((out / "input/scale.cpp").is_file())
            self.assertEqual(metrics["exitCode"], code)
            self.assertEqual([event["event"] for event in metrics["stages"]], ["start", "end"])
            return metrics

    def test_child_records_enabled_and_disabled_with_both_renderers(self):
        enabled = self._child(chunks=True, findings=3)
        self.assertEqual(enabled["exitCode"], 0)
        self.assertEqual(enabled["truncatedRoots"], 3)
        self.assertEqual(enabled["excludedCount"], 93)
        disabled = self._child("disabled", findings=96, usage=False)
        self.assertEqual(disabled["exitCode"], 0)
        self.assertEqual(disabled["statistics"], {})

    def test_child_rejects_missing_artifacts_candidates_usage_and_cli_failure(self):
        self.assertEqual(self._child(artifacts=False)["exitCode"], 1)
        self.assertEqual(self._child(cli_code=7)["exitCode"], 7)
        self.assertIn("候选规模不符", self._child(roots=95)["reason"])
        self.assertEqual(self._child("disabled", findings=96, usage=False, artifacts=False)["exitCode"], 1)
        self.assertIn("候选规模不符", self._child(usage=False)["reason"])
        self.assertEqual(self._child(roots=0)["exitCode"], 1)

    def _run(self, behavior):
        with TemporaryDirectory() as temporary, ExitStack() as guards:
            output = Path(temporary) / "benchmark"
            guards.enter_context(patch.object(runner, "verify_limits", return_value={"cpu": 2}))
            guards.enter_context(patch("builtins.print"))
            seen = []
            def execute(command, **kwargs):
                self.assertEqual(kwargs["timeout"], 300)
                self.assertFalse(kwargs["check"])
                seen.append(command)
                target = Path(command[command.index("--output") + 1])
                if behavior == "timeout":
                    raise subprocess.TimeoutExpired(command, 300)
                if behavior != "missing":
                    references = int(command[command.index("--references") + 1])
                    density = command[command.index("--density") + 1]
                    mode = command[command.index("--mode") + 1]
                    metrics = valid_pair()[0 if mode == "disabled" else 1]
                    scopes = references // 25 if density == "dense" else (references // 25 + 99) // 100
                    metrics.update(references=references, density=density, expectedRoots=24*scopes,
                                   findings=24*scopes, excludedCount=0)
                    if mode == "enabled":
                        metrics["statistics"].update(rootCount=24*scopes, scopeIndexes=scopes)
                    target.mkdir()
                    (target / "metrics.json").write_text(json.dumps(metrics))
                return SimpleNamespace(returncode=9 if behavior == "nonzero" else 0,
                                       stdout="stdout", stderr="stderr")
            guards.enter_context(patch.object(runner.subprocess, "run", side_effect=execute))
            code = runner.run(SimpleNamespace(output=output))
            result = json.loads((output / "summary.json").read_text())
            self.assertEqual(len(seen), 8)
            self.assertEqual(len(result["results"]), 4)
            self.assertTrue(result["relativeComparisonIsDiagnostic"])
            self.assertEqual(result["policy"], "feature-cost-2026-09-24")
            self.assertEqual(len(result["sourceDigest"]), 64)
            self.assertTrue((output / "runtime.json").is_file())
            return code, result

    def test_driver_collects_complete_matrix(self):
        code, result = self._run("normal")
        self.assertEqual(code, 0)
        self.assertTrue(result["passed"])

    def test_driver_retains_all_failures_and_never_stops_at_first_pair(self):
        for behavior in ("timeout", "missing", "nonzero"):
            with self.subTest(behavior=behavior):
                code, result = self._run(behavior)
                self.assertEqual(code, 1)
                self.assertFalse(result["passed"])
                if behavior == "nonzero":
                    self.assertEqual(result["results"][0]["runs"][0]["exitCode"], 9)


if __name__ == "__main__":
    unittest.main()
