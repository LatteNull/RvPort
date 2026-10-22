from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.projection.projector import CompatibleReportProjector
from kb_scanner.projection.renderers import render_html, render_json, render_log

from .support import graph, payload


class FixedMapper:
    def __init__(self, value): self.value = value
    def map(self, *args): return self.value


class RenderProjectorTests(unittest.TestCase):
    def test_renderers_are_deterministic_escape_html_and_disclaim_readiness(self) -> None:
        value = payload()
        value["diagnostics"] = ["中文 <bad>"]
        value["summary"]["readiness"] = {
            "state": "needs_review", "confidence": "medium", "dimensions": {}, "blockingDimensions": [],
            "completeness": {}, "staticScopeOnly": True, "compiled": False, "testsExecuted": False, "trace": {},
        }
        self.assertEqual(render_json(value), render_json(value))
        self.assertEqual(value, json.loads(render_json(value)))
        html = render_html(value).decode()
        self.assertIn("未执行真实编译或测试", html)
        log = render_log(value).decode()
        self.assertIn("compiled=false", log)
        self.assertIn("中文 <bad>", log)

    def test_html_escapes_finding_content(self) -> None:
        args = graph(Path.cwd(), with_assessment=False)
        value = __import__("kb_scanner.projection.mapper", fromlist=["CompatibilityMapper"]).CompatibilityMapper().map(*args)
        value["findings"][0]["snippet"] = "<script>"
        self.assertIn("&lt;script&gt;", render_html(value).decode())

    def test_projector_writes_requested_artifacts_in_compatible_order_and_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); args = list(graph(root)); args[0] = __import__("dataclasses").replace(args[0], formats=("json", "html"))
            args[0].output_dir.mkdir(); (args[0].output_dir / "scan-result.json").write_text("old")
            result = CompatibleReportProjector().project(*args)
            self.assertEqual(CompletionStatus.COMPLETE, result.status)
            self.assertEqual(("scan-result.json", "scan-report.html", "scan.log"), tuple(item.name for item in result.value))
            self.assertEqual("1.0", json.loads((args[0].output_dir / "scan-result.json").read_text())["schemaVersion"])
            self.assertTrue(all(len(item.sha256) == 64 for item in result.value))

    def test_projector_honors_format_and_reports_mapping_failure_without_partial_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); args = list(graph(root)); args[0] = __import__("dataclasses").replace(args[0], formats=("html",))
            result = CompatibleReportProjector().project(*args)
            self.assertEqual(("scan-report.html", "scan.log"), tuple(item.name for item in result.value))
            invalid = payload(); invalid["schemaVersion"] = "2.0"
            failure = CompatibleReportProjector(FixedMapper(invalid)).project(*args)
            self.assertEqual(CompletionStatus.FAILED, failure.status)
            self.assertTrue(failure.diagnostics[0].affects_exit_code)

    def test_publish_failure_restores_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); args = list(graph(root)); output = args[0].output_dir; output.mkdir()
            targets = ("scan-result.json", "scan-report.html", "scan.log")
            for name in targets: (output / name).write_text(f"old-{name}")
            calls = 0
            def replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 4: raise OSError("publish")
                return __import__("os").replace(source, target)
            result = CompatibleReportProjector(replace=replace).project(*args)
            self.assertEqual(CompletionStatus.FAILED, result.status)
            for name in targets: self.assertEqual(f"old-{name}", (output / name).read_text())


if __name__ == "__main__":
    unittest.main()
