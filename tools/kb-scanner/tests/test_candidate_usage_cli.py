"""默认 CLI 的真实语法与工件组件测试，不计入隔离单元覆盖。"""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kb_scanner.cli import main
from kb_scanner.core import StageResult
from kb_scanner.frontends.cpp.frontend import CppFrontend
from kb_scanner.frontends.cpp.clang_adapter import ClangCppAdapter
from kb_scanner.pipeline.composite import CompositeProjectFrontend
from kb_scanner.projection.v2.models import SchemaV2Report
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator


ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "org.rvport.kb-scanner.candidate-usage"
ORACLE = json.loads((ROOT / "tests/fixtures/candidate-usage-oracle.json").read_text())


class CandidateUsageCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "input"
        self.source.mkdir()
        self.sequence = 0

    def scan(self, source, version=None, enabled=True, compile_commands=None):
        (self.source / "usage.cpp").write_bytes(source.encode())
        self.sequence += 1
        out = self.base / f"report-{self.sequence}"
        args = ["scan", "--input", str(self.source), "--rules", str(ROOT / "rulesets/riscv-porting"), "--output", str(out)]
        if version:
            args += ["--schema-version", version]
        if compile_commands:
            args += ["--compile-commands", str(compile_commands)]
        with ExitStack() as guards:
            guards.enter_context(patch("subprocess.run", side_effect=AssertionError("不得执行项目命令")))
            if not enabled:
                guards.enter_context(patch("kb_scanner.analyzers.candidate_usage.analysis.CandidateUsageAnalyzer.analyze",
                    side_effect=lambda context, facts, knowledge, base: StageResult(base)))
            self.assertEqual(0, main(args))
        self.assertEqual(source.encode(), (self.source / "usage.cpp").read_bytes())
        artifacts = {path.name: path.read_bytes() for path in out.iterdir()}
        self.assertEqual({"scan-result.json", "scan-report.html", "scan.log"}, set(artifacts))
        report = json.loads(artifacts["scan-result.json"])
        if version != "1.0":
            V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(report))
        return report, artifacts

    def test_default_cli_generates_and_consumes_real_usage_proofs(self):
        source = ORACLE["cases"][0]["source"]
        before, _ = self.scan(source, enabled=False)
        after, artifacts = self.scan(source)
        audit = after["extensions"][NAMESPACE]
        self.assertGreater(audit["excludedCount"], 0)
        self.assertLess(len(after["findings"]), len(before["findings"]))
        for item in audit["excludedCandidates"]:
            self.assertEqual("excluded", item["status"])
            self.assertEqual("complete", item["producerStatus"])
            self.assertTrue(item["sources"])
            self.assertTrue(all(source["file"] == "usage.cpp" for source in item["sources"]))
        self.assertNotEqual("ready", after["summary"]["readiness"])
        self.assertIn("候选用途审计", artifacts["scan-report.html"].decode())
        explicit, _ = self.scan(source, "2.0")
        self.assertEqual(after, explicit)
        old, _ = self.scan(source, "1.0")
        self.assertEqual("1.0", old["schemaVersion"])
        self.assertNotIn("extensions", old)

    def test_unknown_and_execution_oracles_are_not_excluded(self):
        for case in ORACLE["cases"][1:]:
            with self.subTest(case=case["name"]):
                report, _ = self.scan(case["source"])
                audit = report.get("extensions", {}).get(NAMESPACE, {})
                self.assertEqual(0, audit.get("excludedCount", 0))
                if case["expected"] == "execution-conflict":
                    usage_roots = [root for finding in report["findings"]
                        for root in finding["fact"].get("extensions", {}).get(NAMESPACE, {}).get("roots", ())]
                    self.assertTrue(any(root["statistics"]["conflictCount"] > 0
                        and "usage-known-execution-conflict" in root["reasonCodes"] for root in usage_roots))
                    hits = [f for f in report["findings"] if f["fact"]["symbol"] == "_mm256_setzero_ps"]
                    self.assertTrue(hits)
                    baseline, _ = self.scan(case["source"], enabled=False)
                    old = [f for f in baseline["findings"] if f["fact"]["symbol"] == "_mm256_setzero_ps"]
                    self.assertEqual([f["conclusion"] for f in old], [f["conclusion"] for f in hits])
                for finding in report["findings"]:
                    self.assertFalse(any(step["kind"] in {"classification", "assessment", "semantic_role"}
                        for step in finding["evidenceChain"]["steps"]))

    def test_no_candidate_artifacts_are_byte_identical(self):
        source = "int sum(int a, int b) { return a + b; }\n"
        for version in (None, "1.0"):
            with self.subTest(version=version):
                _, before = self.scan(source, version, enabled=False)
                _, after = self.scan(source, version)
                self.assertEqual(before, after)

    def test_templates_preprocessing_and_pointer_aliases_fail_closed(self):
        cases = {
            "template": "template<class T> void f(T value) { enum Format { FORMAT_X86=1 }; int kind=FORMAT_X86; if(kind==FORMAT_X86) { value(); } }",
            "address": "void f() { enum Format { FORMAT_X86=1 }; int kind=FORMAT_X86; int *p=&kind; *p=0; }",
            "volatile": "void f() { enum Format { FORMAT_X86=1 }; volatile int kind=FORMAT_X86; if(kind==FORMAT_X86) {} }",
            "error": "void f() { enum Format { FORMAT_X86=1 }; int kind=FORMAT_X86; if(kind==FORMAT_X86) { broken( ; } }",
            "local-macro": "void f() { enum Format { FORMAT_X86=1 };\n#define FORMAT_X86 external()\nint kind=FORMAT_X86; char label[1]; if(kind==FORMAT_X86) { label[0]='x'; } }",
        }
        for name, source in cases.items():
            with self.subTest(case=name):
                report, _ = self.scan(source)
                self.assertGreater(report.get("extensions", {}).get(NAMESPACE, {}).get("statistics", {}).get("rootCount", 0), 0)
                self.assertEqual(0, report.get("extensions", {}).get(NAMESPACE, {}).get("excludedCount", 0))

    def test_cross_translation_unit_escape_does_not_borrow_local_proof(self):
        (self.source / "other.cpp").write_text(ORACLE["cases"][0]["source"].replace("void f", "void g"))
        source = ORACLE["cases"][8]["source"]
        report, _ = self.scan(source)
        audit = report["extensions"][NAMESPACE]
        self.assertGreater(audit["excludedCount"], 0)
        self.assertTrue(all(s["file"] == "other.cpp" for item in audit["excludedCandidates"] for s in item["sources"]))
        escaped = [finding for finding in report["findings"]
            if NAMESPACE in finding["fact"].get("extensions", {})]
        self.assertTrue(escaped)
        self.assertTrue(all(root["status"] == "unknown" for finding in escaped
            for root in finding["fact"]["extensions"][NAMESPACE]["roots"]))

    def test_clang_multiple_configurations_do_not_borrow_unconfigured_inventory(self):
        database = self.base / "compile_commands.json"
        database.write_text(json.dumps([{"directory": str(self.source), "file": str(self.source / "usage.cpp"),
            "arguments": ["clang++", "-std=c++17", f"-DMODE={mode}", "-c", str(self.source / "usage.cpp")]}
            for mode in (0, 1)]))
        source = ORACLE["cases"][0]["source"]
        for clang in (None, ClangCppAdapter()):
            with self.subTest(clang=clang is not None), patch("kb_scanner.pipeline.default.CompositeProjectFrontend",
                return_value=CompositeProjectFrontend(cpp=CppFrontend(clang=clang))):
                report, _ = self.scan(source, compile_commands=database)
            audit = report["extensions"][NAMESPACE]
            self.assertGreater(audit["statistics"]["rootCount"], 0)
            self.assertEqual(0, audit["excludedCount"])
            reasons = {reason for finding in report["findings"]
                for root in finding["fact"].get("extensions", {}).get(NAMESPACE, {}).get("roots", ())
                for reason in root["reasonCodes"]}
            self.assertIn("usage-configuration-unknown", reasons)
            self.assertFalse(any("clang.unavailable" in d["code"] for d in report["diagnostics"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
