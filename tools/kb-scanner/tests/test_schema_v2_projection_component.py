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
FIXTURE = ROOT / "tests/fixtures/source-evidence-chain"
RULES = ROOT / "rulesets/riscv-porting"
SCHEMA = json.loads((ROOT / "schemas/scan-result-v2.schema.json").read_text(encoding="utf-8"))


class SchemaV2ProjectionComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE.is_dir():
            raise AssertionError("仓库内源码证据链夹具缺失")
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

    def test_local_intrinsic_keeps_source_path_and_self_contained_chain(self):
        payload = self.payloads[0]
        intrinsic = [item for item in payload["findings"] if item["fact"]["symbol"] == "_mm256_setzero_si256"]
        self.assertEqual(1, len(intrinsic))
        chain = intrinsic[0]["evidenceChain"]
        self.assertEqual("complete", chain["status"])
        steps = {step["id"]: step for step in chain["steps"]}
        self.assertEqual({"Makefile", "main.cpp", "wrapper.h"},
                         {steps[sid]["source"]["file"] for sid in chain["primaryPath"]})
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
