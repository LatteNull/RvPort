from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets/riscv-porting"
CONSTEXPR = ROOT / "tests/fixtures/riscv-porting/cpp_x86_constexpr_arch_branch/src"
MATRIX = ROOT / "tests/fixtures/architecture-enum"


def scan(root: Path, version: str | None = None):
    output = tempfile.TemporaryDirectory(prefix="kb-architecture-enum-")
    request = ScanRequest(str(root), str(RULES), output.name, **({} if version is None else {"schema_version": version}))
    result = create_default_application().run(request)
    payload = json.loads((Path(output.name) / "scan-result.json").read_text(encoding="utf-8"))
    return output, result, payload


class ArchitectureEnumAnalysisTests(unittest.TestCase):
    def test_constexpr_default_v2_and_explicit_v1_are_traceable(self) -> None:
        v2_output, v2_result, v2 = scan(CONSTEXPR)
        v1_output, v1_result, v1 = scan(CONSTEXPR, "1.0")
        self.addCleanup(v2_output.cleanup)
        self.addCleanup(v1_output.cleanup)
        self.assertEqual((0, 0), (v2_result.exit_code, v1_result.exit_code))
        self.assertEqual(["scan-result.json", "scan-report.html", "scan.log"], [item.name for item in v2_result.artifacts])
        self.assertEqual(1, v2["summary"]["findings"])
        finding = v2["findings"][0]
        self.assertEqual("architecture_probe", finding["fact"]["kind"])
        self.assertEqual("enum_member_reference", finding["fact"]["extensions"]["org.rvport.kb-scanner.architecture-enum"]["evidenceKind"])
        self.assertTrue({"contains", "selects"}.issubset({item["kind"] for item in finding["evidenceChain"]["edges"]}))
        self.assertFalse(any(item["code"] == "normalization.unsupported-evidence-kind" for item in v2["diagnostics"]))
        self.assertEqual("CPP.X86.CONSTEXPR_ARCH_BRANCH", v1["findings"][0]["rule_id"])
        self.assertEqual("avx2", v1["findings"][0]["symbol"])

    def test_matrix_covers_actionable_unknown_switch_recovery_and_near_miss(self) -> None:
        output, result, payload = scan(MATRIX)
        self.addCleanup(output.cleanup)
        self.assertEqual(0, result.exit_code)
        candidates = [item for item in payload["findings"] if item["conclusion"]["findingType"] == "architecture_enum_candidate"]
        self.assertTrue(any(item["conclusion"]["reason"] == "guarded-x86-enum-dependency-target-unknown" and item["conclusion"]["actionable"] for item in candidates))
        self.assertTrue(any(item["conclusion"]["status"] == "unknown" for item in candidates))
        self.assertTrue(any("selects" in {edge["kind"] for edge in item["evidenceChain"]["edges"]} for item in candidates))
        symbols = {item["fact"]["symbol"] for item in candidates}
        self.assertNotIn("Mode::avx2_counted", symbols)
        self.assertFalse(any(symbol and "arm_neon" in symbol for symbol in symbols))

    def test_inventory_docs_and_frozen_compiler_facts_are_present(self) -> None:
        inventory = json.loads((ROOT / "tests/architecture-enum-test-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual("kb-scanner-test", inventory["container"])
        self.assertEqual({"linePercent": 90.0, "branchPercent": 90.0}, inventory["coverageThresholds"])
        for module, mapping in inventory["modules"].items():
            self.assertTrue((ROOT / "kb_scanner" / module).is_file(), module)
            self.assertTrue((ROOT / mapping["unit"]).is_file(), module)
        self.assertTrue((ROOT / "docs/analysis-capabilities.md").is_file())
        expected = {
            "clang-x86-entries.json": "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7",
            # 开源迁移只将 source.path 脱敏为相对路径；事实内容保持不变。
            "gcc-x86-entries.json": "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191",
        }
        for name, digest in expected.items():
            self.assertEqual(digest, hashlib.sha256((RULES / "generated" / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
