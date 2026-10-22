from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from tests.schema_v2_contract import reference_errors


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("/fixtures/avx-avx2-example-code/source")
RULES = ROOT / "rulesets/riscv-porting"
SCHEMA = json.loads((ROOT / "schemas/scan-result-v2.schema.json").read_text(encoding="utf-8"))


class SchemaV2ProjectionComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE.is_dir():
            raise AssertionError("AVX fixture must be mounted read-only")
        cls.outputs = []
        cls.payloads = []
        cls.bytes = []
        for version in (None, "2.0"):
            output = tempfile.TemporaryDirectory()
            request = ScanRequest(str(FIXTURE), str(RULES), output.name, **({} if version is None else {"schema_version": version}))
            result = create_default_application().run(request)
            if result.exit_code != 0:
                raise AssertionError(result.diagnostics)
            content = (Path(output.name) / "scan-result.json").read_bytes()
            cls.outputs.append(output)
            cls.bytes.append(content)
            cls.payloads.append(json.loads(content))

    @classmethod
    def tearDownClass(cls) -> None:
        for output in cls.outputs:
            output.cleanup()

    def test_default_and_explicit_v2_are_byte_identical_and_schema_valid(self):
        self.assertEqual(self.bytes[0], self.bytes[1])
        payload = self.payloads[0]
        self.assertEqual([], [item.message for item in Draft202012Validator(SCHEMA).iter_errors(payload)])
        self.assertEqual([], reference_errors(payload))
        self.assertEqual("2.0", payload["schemaVersion"])

    def test_avx_findings_keep_audited_counts_and_self_contained_chains(self):
        payload = self.payloads[0]
        self.assertEqual(828, payload["summary"]["findings"])
        self.assertEqual(783, payload["summary"]["blocking"])
        self.assertEqual(779, payload["summary"]["portabilityGaps"])
        flags = [item for item in payload["findings"] if item["fact"]["kind"] in {"compiler_flag", "build_argument"}]
        self.assertEqual(4, len(flags))
        self.assertEqual(24, sum(len(item["occurrences"]) for item in flags))
        macro_findings = [item for item in payload["findings"] if item["fact"]["kind"] == "macro_replacement"]
        self.assertEqual(18, len(macro_findings))
        self.assertTrue(any(
            {"macro_definition", "macro_replacement"}.issubset({
                next(step["kind"] for step in item["evidenceChain"]["steps"] if step["id"] == step_id)
                for step_id in item["evidenceChain"]["primaryPath"]
            })
            for item in macro_findings
        ))
        for finding in payload["findings"]:
            chain = finding["evidenceChain"]
            self.assertEqual([], chain["impactStepIds"])
            self.assertFalse({"classification", "assessment"} & {step["kind"] for step in chain["steps"]})
            self.assertFalse({step["id"] for step in chain["steps"] if step["kind"] == "knowledge_match"} & set(chain["primaryPath"]))
            self.assertIn(finding["primaryOccurrenceId"], {item["id"] for item in finding["occurrences"]})
            self.assertTrue(finding["evidenceChain"]["primaryPath"])
            self.assertTrue(finding["fact"]["primaryLocation"]["context"]["lines"])


if __name__ == "__main__":
    unittest.main()
