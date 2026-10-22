from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"

RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schemaVersion", "tool", "rulePack", "project", "summary", "findings", "diagnostics"],
    "properties": {
        "schemaVersion": {"const": "1.0"},
        "tool": {"type": "object"},
        "rulePack": {"type": "object"},
        "project": {"type": "object"},
        "summary": {"type": "object"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_id", "location", "context", "trace"],
                "properties": {"trace": {"type": "object"}},
            },
        },
        "diagnostics": {"type": "array"},
    },
}


class OutputContractTests(unittest.TestCase):
    def test_schema_and_three_artifacts_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            output = Path(tmp) / "out"
            project.mkdir()
            (project / "main.c").write_text("#include <immintrin.h>\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "kb_scanner",
                    "scan",
                    "--input",
                    str(project),
                    "--rules",
                    str(RULES),
                    "--output",
                    str(output),
                    "--format",
                    "json,html",
                    "--schema-version",
                    "1.0",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"scan-result.json", "scan-report.html", "scan.log"},
            )
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))
            Draft202012Validator(RESULT_SCHEMA).validate(payload)
            self.assertEqual(
                set(payload),
                {"schemaVersion", "tool", "rulePack", "project", "summary", "findings", "diagnostics"},
            )
            self.assertTrue(payload["findings"])
            self.assertTrue(all(isinstance(item["trace"], dict) for item in payload["findings"]))


if __name__ == "__main__":
    unittest.main()
