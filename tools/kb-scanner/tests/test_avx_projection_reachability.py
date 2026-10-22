from __future__ import annotations

from collections import Counter
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.projection.contract import validate_payload


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("/fixtures/avx-avx2-example-code/source")
RULES = ROOT / "rulesets" / "riscv-porting"
MANUAL_BASELINE = ROOT / "tests" / "fixtures" / "evidence-graph" / "avx-manual-baseline.json"
BUILD_BASELINE = ROOT / "tests" / "fixtures" / "build-selection" / "avx-make-baseline.json"


def relative_path(value: str) -> str:
    normalized = PurePosixPath(value).as_posix()
    prefix = PurePosixPath(FIXTURE).as_posix().rstrip("/") + "/"
    return normalized.removeprefix(prefix)


class AvxProjectionReachabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE.is_dir():
            raise AssertionError("AVX fixture must be mounted read-only by compose.test.yml")
        cls.manual = json.loads(MANUAL_BASELINE.read_text(encoding="utf-8"))
        cls.build = json.loads(BUILD_BASELINE.read_text(encoding="utf-8"))
        cls.output = tempfile.TemporaryDirectory()
        result = create_default_application().run(
            ScanRequest(str(FIXTURE), str(RULES), cls.output.name, formats=("json",), schema_version="1.0")
        )
        if result.exit_code != 0:
            raise AssertionError(f"AVX default scan failed: {result.exit_code}")
        cls.payload = json.loads((Path(cls.output.name) / "scan-result.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.output.cleanup()

    def test_schema_and_manual_fact_counts_remain_compatible(self) -> None:
        validate_payload(self.payload)
        counts = Counter(item["rule_id"] for item in self.payload["findings"])
        audited = self.manual["auditedCounts"]
        self.assertEqual(audited["x86Headers"], counts["C_CPP.X86.HEADER"])
        self.assertEqual(audited["x86VectorTypes"], counts["C_CPP.X86.VECTOR_TYPE"])
        self.assertEqual(audited["directIntrinsicCalls"], counts["C_CPP.X86.INTRINSIC_CALL"])
        self.assertEqual(audited["commentHints"], counts["COMMENT.ARCH.HINT"])
        self.assertEqual(
            audited["replacementTerminalIntrinsicReferences"],
            counts["C_CPP.X86.MACRO_EXPANDS_TO_INTRINSIC"],
        )
        self.assertEqual(4, counts["C_CPP.X86.COMPILER_FLAG"])
        self.assertEqual(828, self.payload["summary"]["findings"])
        self.assertTrue(
            all(item["symbol"] for item in self.payload["findings"] if item["rule_id"] != "COMMENT.ARCH.HINT")
        )

    def test_macro_terminal_findings_close_definition_relation_span_and_symbol(self) -> None:
        findings = [
            item
            for item in self.payload["findings"]
            if item["rule_id"] == "C_CPP.X86.MACRO_EXPANDS_TO_INTRINSIC"
        ]
        definition_ids = {
            evidence["id"]
            for finding in findings
            for evidence in finding["trace"]["evidence"]
            if evidence["kind"] == "macro_definition"
        }
        self.assertEqual(self.manual["auditedCounts"]["functionLikeMacroDefinitions"], len(definition_ids))
        for finding in findings:
            trace = finding["trace"]
            kinds = {item["kind"] for item in trace["evidence"]}
            self.assertIn("macro_definition", kinds)
            self.assertIn("macro_replacement_token", kinds)
            self.assertEqual("complete", trace["referenceClosure"]["status"])
            self.assertTrue(finding["symbol"].startswith("_mm"))
            self.assertTrue(any(item["kind"] == "expands_to" for item in trace["relations"]))
            self.assertTrue(all(item.get("location", {}).get("end") for item in trace["evidence"] if item.get("location")))

    def test_representative_primary_spans_match_corrected_manual_oracle(self) -> None:
        intrinsic_findings = [
            item for item in self.payload["findings"] if item["rule_id"] == "C_CPP.X86.INTRINSIC_CALL"
        ]
        for expected in self.manual["representativeInvocations"]:
            matches = [
                item
                for item in intrinsic_findings
                if relative_path(item["file"]) == expected["path"]
                and item["symbol"] == expected["name"]
                and item["line"] == expected["span"]["start"][0]
            ]
            self.assertEqual(1, len(matches), expected)
            span = matches[0]["trace"]["primarySpan"]
            self.assertEqual(expected["span"]["start"], [span["start"]["line"], span["start"]["column"]])
            self.assertEqual(expected["span"]["end"], [span["end"]["line"], span["end"]["column"]])

    def test_all_24_build_occurrences_are_recoverable_from_four_findings(self) -> None:
        findings = [
            item for item in self.payload["findings"] if item["rule_id"] == "C_CPP.X86.COMPILER_FLAG"
        ]
        actual = {
            (
                relative_path(occurrence["span"]["file"]),
                occurrence["span"]["start"]["line"],
                occurrence["value"],
                occurrence["span"]["start"]["column"],
                occurrence["span"]["end"]["column"],
                occurrence["configuration"],
                occurrence["selectionStatus"],
            )
            for finding in findings
            for occurrence in finding["trace"]["occurrences"]
        }
        expected = {
            (
                item["path"], item["line"], item["flag"], item["startColumn"], item["endColumn"],
                "default", item["expectedStatus"],
            )
            for item in self.build["entries"]
        }
        self.assertEqual(self.build["expectedCount"], sum(item["trace"]["occurrenceCount"] for item in findings))
        self.assertEqual(expected, actual)
        self.assertTrue(all(item["trace"]["occurrenceCount"] == 6 for item in findings))

    def test_reachability_classification_gap_and_readiness_share_one_proof_state(self) -> None:
        summary = self.payload["summary"]
        readiness = summary["readiness"]
        self.assertEqual(783, summary["blocking"])
        self.assertEqual(779, summary["portabilityGaps"])
        self.assertEqual("x86_only", readiness["state"])
        self.assertEqual("high", readiness["confidence"])
        self.assertEqual("satisfied", readiness["dimensions"]["target_reachability"])
        self.assertEqual("issue", readiness["dimensions"]["x86_dependency"])
        self.assertEqual("issue", readiness["dimensions"]["riscv_or_generic_alternative"])
        self.assertEqual(
            ["x86_dependency", "riscv_or_generic_alternative"], readiness["blockingDimensions"]
        )
        self.assertTrue(readiness["completeness"]["selectedX86Dependency"])
        self.assertTrue(readiness["staticScopeOnly"])
        self.assertFalse(readiness["compiled"])
        self.assertFalse(readiness["testsExecuted"])
        macro_findings = [
            item
            for item in self.payload["findings"]
            if item["rule_id"] == "C_CPP.X86.MACRO_EXPANDS_TO_INTRINSIC"
        ]
        self.assertTrue(all(item["is_actionable"] and item["is_blocking"] for item in macro_findings))
        self.assertTrue(all(item["finding_type"] == "portability_gap" for item in macro_findings))
        self.assertTrue(
            all(
                any(relation["kind"] == "depends_on" for relation in item["trace"]["relations"])
                for item in macro_findings
            )
        )

    def test_unresolved_include_diagnostics_are_aggregated_without_losing_provenance(self) -> None:
        self.assertEqual(2, len(self.payload["diagnostics"]))
        aggregate_messages = [item for item in self.payload["diagnostics"] if "aggregate=" in item]
        self.assertEqual(1, len(aggregate_messages))
        aggregate = json.loads(aggregate_messages[0].split("aggregate=", 1)[1])
        self.assertEqual("graph.include-unresolved-include", aggregate["code"])
        self.assertEqual("unresolved-include", aggregate["reason"])
        self.assertEqual("includes", aggregate["relationKind"])
        self.assertEqual(74, aggregate["count"])
        self.assertEqual(74, len(aggregate["locations"]))
        self.assertEqual(74, len(aggregate["referenceIds"]))
        self.assertEqual(74, len(set(aggregate["locations"])))
        self.assertEqual(74, len(set(aggregate["referenceIds"])))
        self.assertFalse(any("ambiguous-include" in item for item in self.payload["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
