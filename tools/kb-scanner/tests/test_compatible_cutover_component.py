from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner import cli
from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.projection.contract import validate_payload


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets/riscv-porting"


class CompatibleCutoverComponentTests(unittest.TestCase):
    def test_real_cli_preserves_scan_options_on_the_staged_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; project.mkdir()
            output = Path(tmp) / "out"
            (project / "main.c").write_text("// x86 fallback\nint f(void){return 0;}\n")
            ignored = project / "vendor"; ignored.mkdir()
            (ignored / "x86.cpp").write_text("#include <immintrin.h>\n")
            database = project / "commands.json"
            database.write_text(json.dumps([{
                "directory": str(project),
                "file": "main.c",
                "arguments": ["cc", "-D__riscv", "-c", "main.c"],
            }]))
            exit_code = cli.main([
                "scan", "--input", str(project), "--rules", str(RULES), "--output", str(output),
                "--language", "c", "--exclude", ".git", "--exclude-path", "vendor",
                "--format", "json", "--context-infer", "auto", "--target-arch", "riscv64",
                "--include-inactive-branches", "--no-comment-hints", "--compile-commands", str(database),
                "--locale", "en-US",
                "--schema-version", "1.0",
            ])
            payload = json.loads((output / "scan-result.json").read_text())
            artifact_names = {item.name for item in output.iterdir()}
        self.assertEqual(0, exit_code)
        self.assertEqual("source_context_with_compile_database", payload["project"]["scanMode"])
        self.assertEqual("riscv64", payload["project"]["targetArch"])
        self.assertFalse(any(item["rule_id"] == "COMMENT.ARCH.HINT" for item in payload["findings"]))
        self.assertFalse(any("vendor" in item["file"] for item in payload["findings"]))
        self.assertEqual({"scan-result.json", "scan.log"}, artifact_names)

    def test_default_pipeline_writes_compatible_static_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; project.mkdir()
            output = Path(tmp) / "out"
            (project / "main.c").write_text("#include <immintrin.h>\nint f(__m256 a){return _mm256_movemask_ps(a);}\n")
            (project / "Makefile").write_text("CFLAGS = -mavx2\n")
            result = create_default_application().run(ScanRequest(str(project), str(RULES), str(output), schema_version="1.0"))
            payload = json.loads((output / "scan-result.json").read_text())
            validate_payload(payload)
            self.assertEqual(0, result.exit_code)
            self.assertEqual(["scan-result.json", "scan-report.html", "scan.log"], [item.name for item in result.artifacts])
            self.assertTrue({"C_CPP.X86.HEADER", "C_CPP.X86.INTRINSIC_CALL", "C_CPP.X86.COMPILER_FLAG"}.issubset({item["rule_id"] for item in payload["findings"]}))
            self.assertTrue(all(Path(item["file"]).is_absolute() for item in payload["findings"] if item["file"] != "<project>"))
            self.assertTrue(payload["summary"]["readiness"]["staticScopeOnly"])
            self.assertFalse(payload["summary"]["readiness"]["compiled"])
            self.assertFalse(payload["summary"]["readiness"]["testsExecuted"])

    def test_json_only_still_writes_log_and_never_writes_into_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; project.mkdir(); (project / "portable.c").write_text("int f(void){return 0;}\n")
            before = sorted(item.name for item in project.iterdir())
            output = Path(tmp) / "out"
            result = create_default_application().run(ScanRequest(str(project), str(RULES), str(output), formats=("json",), schema_version="1.0"))
            self.assertEqual(0, result.exit_code)
            self.assertEqual(["scan-result.json", "scan.log"], [item.name for item in result.artifacts])
            self.assertEqual(before, sorted(item.name for item in project.iterdir()))

    def test_malicious_build_text_is_not_executed(self) -> None:
        marker = Path("/tmp/kb-scanner-must-not-run")
        self.assertFalse(marker.exists())
        fixture = ROOT / "tests/fixtures/classification-assessment/malicious"
        with tempfile.TemporaryDirectory() as tmp:
            result = create_default_application().run(ScanRequest(str(fixture), str(RULES), tmp, formats=("json",), schema_version="1.0"))
        self.assertEqual(0, result.exit_code)
        self.assertFalse(marker.exists())

    def test_x86_branch_with_riscv_sibling_is_guarded_with_compatible_trace(self) -> None:
        source_text = """#if defined(__x86_64__)\n#include <immintrin.h>\n#elif defined(__riscv)\nint f(void){return 0;}\n#endif\n"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; project.mkdir(); (project / "simd.c").write_text(source_text)
            output = Path(tmp) / "out"
            result = create_default_application().run(ScanRequest(str(project), str(RULES), str(output), include_inactive_branches=True, schema_version="1.0"))
            payload = json.loads((output / "scan-result.json").read_text())
        guarded = [item for item in payload["findings"] if item["rule_id"] == "C_CPP.X86.HEADER"]
        self.assertEqual(0, result.exit_code)
        self.assertTrue(guarded)
        self.assertTrue(all(item["finding_type"] == "guarded" and not item["is_blocking"] for item in guarded))
        self.assertTrue(all(item["branch_role"] == "x86" for item in guarded))
        self.assertTrue(any(item["compatible_branch_kind"] == "riscv" for item in guarded))
        self.assertTrue(any("__x86_64__" in item["condition_macros"] for item in guarded))


if __name__ == "__main__":
    unittest.main()
