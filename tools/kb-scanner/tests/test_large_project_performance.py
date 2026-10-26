"""Small offline compatibility gate; full libarchive is an explicit target."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests.tree_sitter_native_support import run_scanner_process


ROOT = Path(__file__).resolve().parents[1]


class PerformanceCompatibilityTests(unittest.TestCase):
    def test_container_command_enforces_isolation_and_exit_propagation(self):
        launcher = (ROOT / "tests/run-performance-container.ps1").read_text()
        for fragment in ("'--cpus', '2'", "'--memory', '2g'", "'--memory-swap', '2g'",
                         "'--network', 'none'", "'--read-only'", "'--cap-drop', 'ALL'",
                         "target=/fixture,readonly", "target=/workspace/tools/kb-scanner,readonly",
                         "$scanExit = $LASTEXITCODE", "exit $scanExit", "docker rm -f $createdId",
                         "{{json .State}}", "if ($Profile)"):
            self.assertIn(fragment, launcher)
        self.assertNotIn("compose", launcher.lower())
        self.assertNotIn("docker build", launcher.lower())

    def test_v1_v2_match_reviewed_bilingual_suggestion_baseline(self):
        audit = json.loads((ROOT / "tests/fixtures/open-source-regression-baseline.json").read_text())
        expected = audit["after"]
        # 当前快照独立冻结，早期风险与双语建议账本仍保留。
        for version in expected:
            with tempfile.TemporaryDirectory() as raw:
                out = Path(raw)
                result = run_scanner_process(ROOT / "tests/fixtures/architecture-candidate-noise",
                                             ROOT / "rulesets/riscv-porting", out, schema_version=version,
                                             timeout_seconds=60)
                self.assertEqual(0, result.returncode, result)
                payload = json.loads((out / "scan-result.json").read_text())
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
                self.assertEqual(expected[version], digest)
