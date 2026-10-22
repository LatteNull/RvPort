from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from kb_scanner.adapters.legacy import create_legacy_application
from kb_scanner.core import CompletionStatus, ScanRequest


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"


def run_cli(project: Path, output: Path, rules: Path = RULES, *extra: str) -> subprocess.CompletedProcess[str]:
    result = create_legacy_application().run(
        ScanRequest(
            str(project), str(rules), str(output),
            include_inactive_branches="--include-inactive-branches" in extra,
        )
    )
    return subprocess.CompletedProcess(["legacy-oracle"], result.exit_code, "", "\n".join(item.message for item in result.diagnostics))


class LegacyPipelineCompatibilityTests(unittest.TestCase):
    def test_non_scan_subcommands_keep_their_existing_contract(self) -> None:
        version = subprocess.run(
            [sys.executable, "-m", "kb_scanner", "version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        validate = subprocess.run(
            [sys.executable, "-m", "kb_scanner", "validate-rules", "--rules", str(RULES)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        listed = subprocess.run(
            [sys.executable, "-m", "kb_scanner", "list-rules", "--rules", str(RULES)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(version.returncode, 0)
        self.assertEqual(version.stdout.strip(), "0.1.0")
        self.assertEqual(validate.returncode, 0)
        self.assertIn("规则数量:", validate.stdout)
        self.assertIn("知识包: riscv-porting-rules@2026.06", validate.stdout)
        self.assertEqual(listed.returncode, 0)
        self.assertIn("C_CPP.X86.HEADER\tcode-owned\tversion=1", listed.stdout)

    def test_legacy_oracle_preserves_semantic_finding_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            output = Path(tmp) / "out"
            project.mkdir()
            (project / "main.cpp").write_text(
                "#ifdef USE_FAST_PATH\n#include <immintrin.h>\n#endif\n",
                encoding="utf-8",
            )
            result = create_legacy_application().run(
                ScanRequest(str(project), str(RULES), str(output))
            )
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual([item.name for item in result.artifacts], ["scan-result.json", "scan-report.html", "scan.log"])
        self.assertTrue(all(len(item.sha256) == 64 for item in result.artifacts))
        finding = next(item for item in payload["findings"] if item["rule_id"] == "C_CPP.X86.HEADER")
        self.assertEqual(finding["finding_type"], "portability_gap")
        self.assertEqual(finding["severity"], "high")
        self.assertTrue(finding["is_blocking"])
        self.assertEqual(finding["line"], 2)
        self.assertEqual(finding["condition_macros"], ["USE_FAST_PATH"])
        self.assertEqual(finding["trace"]["include"], "immintrin.h")
        self.assertIn("自定义宏 USE_FAST_PATH", finding["reason"])
        self.assertIn("RISC-V", finding["suggestion"])
        self.assertEqual(
            set(payload),
            {"schemaVersion", "tool", "rulePack", "project", "summary", "findings", "diagnostics"},
        )

    def test_compile_context_failure_remains_nonfatal_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            output = Path(tmp) / "out"
            project.mkdir()
            (project / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
            (project / "compile_commands.json").write_text("{not-json", encoding="utf-8")
            completed = run_cli(project, output)
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(payload["project"]["scanMode"], "source_context")
        self.assertIn("compile_commands.json 加载失败", payload["diagnostics"][0])
        self.assertEqual(payload["diagnostics"][-1], "compile_commands.json 不可用，已继续使用源码上下文推导。")

    def test_rule_load_failure_keeps_exit_one_and_still_projects_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            output = Path(tmp) / "out"
            rules = Path(tmp) / "ruleset"
            project.mkdir()
            (rules / "rules").mkdir(parents=True)
            (project / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
            (rules / "manifest.yaml").write_text("id: broken\nversion: 1\n", encoding="utf-8")
            (rules / "rules" / "broken.yaml").write_text("- not-an-object\n", encoding="utf-8")
            completed = run_cli(project, output, rules)
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))
            artifact_names = {item.name for item in output.iterdir()}

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(artifact_names, {"scan-result.json", "scan-report.html", "scan.log"})
        self.assertTrue(any("规则必须是对象" in item for item in payload["diagnostics"]))

    def test_guarded_portable_path_comment_hint_rpm_and_compile_trace_stay_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            output = Path(tmp) / "out"
            project.mkdir()
            (project / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #if defined(__AVX2__)
                    #include <immintrin.h>
                    #elif defined(__riscv)
                    int add(void) { return 1; }
                    #else
                    int add(void) { return 0; }
                    #endif
                    // x86 optimization note
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (project / "package.spec").write_text("Name: demo\nExclusiveArch: x86_64\n", encoding="utf-8")
            (project / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(project),
                            "file": str(project / "simd.c"),
                            "arguments": ["clang", "-mavx2", "-c", "simd.c"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            completed = run_cli(project, output, RULES, "--include-inactive-branches")
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        guarded = [item for item in payload["findings"] if item["finding_type"] == "guarded"]
        self.assertTrue(guarded)
        self.assertTrue(all(not item["is_blocking"] for item in guarded))
        self.assertEqual({item["compatible_branch_kind"] for item in guarded}, {"riscv"})
        self.assertTrue(any(item["finding_type"] == "hint" and item["source_kind"] == "comment" for item in payload["findings"]))
        self.assertTrue(any(item["rule_id"] == "RPM_SPEC.ARCH.CONSTRAINT" for item in payload["findings"]))
        compile_findings = [item for item in payload["findings"] if item["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertTrue(any(item["trace"]["compileCommand"]["token"] == "-mavx2" for item in compile_findings))


if __name__ == "__main__":
    unittest.main()
