"""Real schema/CLI and fixed-snapshot component contracts, not unit coverage."""
import copy
from dataclasses import replace
import hashlib
import html
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from kb_scanner.cli import main
from kb_scanner.core import CompletionStatus
from kb_scanner.projection.v2.models import SchemaV2Report
from kb_scanner.projection.v2.projector import SchemaV2ReportProjector
from kb_scanner.projection.v2.renderers import render_json
from tests.schema_v2_contract import reference_errors
from tests.unit.schema_v2_projection.support import graph_with_source


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
PAIRS = json.loads((FIXTURES / "bilingual-suggestions/expected-pairs.json").read_text(encoding="utf-8"))
LEDGER = json.loads((FIXTURES / "cmake-risk-report-differential.json").read_text(encoding="utf-8"))
LEDGER["fixtures"].update(json.loads((FIXTURES / "function-multiversion-report-differential.json").read_text(encoding="utf-8"))["fixtures"])
HISTORICAL_LEDGER = copy.deepcopy(LEDGER)
LEDGER["fixtures"].update(json.loads((FIXTURES / "candidate-usage-report-differential.json").read_text(encoding="utf-8"))["fixtures"])
MACRO_LEDGER = json.loads((FIXTURES / "macro-build-effect-report-differential.json").read_text(encoding="utf-8"))
LEDGER["fixtures"].update(MACRO_LEDGER["fixtures"])
SCHEMA = json.loads((ROOT / "schemas/scan-result-v2.schema.json").read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class BilingualReaderContractTests(unittest.TestCase):
    def test_historical_reader_and_materialized_current_pairs(self):
        original = json.loads((FIXTURES / "schema-v2/complete.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(SCHEMA)
        validator.validate(original)
        self.assertNotIn("suggestion_en", json.loads(render_json(SchemaV2Report.model_validate(original)))["findings"][0]["conclusion"])
        for key, pair in PAIRS.items():
            with self.subTest(key=key):
                current = copy.deepcopy(original)
                current["findings"][0]["conclusion"].update(suggestion=pair["zh"], suggestion_en=pair["en"])
                validator.validate(current)
                model = SchemaV2Report.model_validate(current)
                model.findings[0].conclusion.require_bilingual_suggestions()
                self.assertEqual([], reference_errors(current))
                self.assertEqual(pair["en"], json.loads(render_json(model))["findings"][0]["conclusion"]["suggestion_en"])
        for invalid in (None, "", " \t\n", 3, False, [], {}):
            with self.subTest(invalid=invalid):
                current = copy.deepcopy(original)
                current["findings"][0]["conclusion"]["suggestion_en"] = invalid
                self.assertTrue(list(validator.iter_errors(current)))
                with self.assertRaises(ValidationError):
                    SchemaV2Report.model_validate(current)

    def test_fixed_snapshots_preserve_uncertainty_and_gap_semantics(self):
        cases = [("blocking_issue", "complete", "x86_intrinsic_reference", "blocking"),
                 ("blocking_issue", "partial", "x86_intrinsic_reference", "unknown"),
                 ("blocking_issue", "ambiguous", "x86_intrinsic_reference", "unknown"),
                 ("unknown", "unknown", "x86_intrinsic_reference", "unknown"),
                 ("guarded_inactive", "complete", "x86_intrinsic_reference", "inactive"),
                 ("hint", "complete", "x86_comment_hint", "hint"),
                 ("actionable_non_blocking", "complete", "missing_riscv_selection_path", "selection_gap"),
                 ("actionable_non_blocking", "complete", "riscv_test_coverage_gap", "test_gap")]
        for impact, status, kind, key in cases:
            with self.subTest(key=key, status=status), tempfile.TemporaryDirectory() as temp:
                values = list(graph_with_source(Path(temp)))
                observation = replace(values[6].observations[0], kind=kind)
                classification = replace(values[7].classifications[0], impact=impact, metadata={"completeness": status})
                values[6] = replace(values[6], observations=(observation,))
                values[7] = replace(values[7], observations=(observation,), classifications=(classification,))
                result = SchemaV2ReportProjector().project(*values)
                self.assertEqual(CompletionStatus.COMPLETE, result.status, result.diagnostics)
                output = json.loads((Path(temp) / "out/scan-result.json").read_text(encoding="utf-8"))
                conclusion = output["findings"][0]["conclusion"]
                self.assertEqual(PAIRS[key]["zh"], conclusion["suggestion"])
                self.assertEqual(PAIRS[key]["en"], conclusion["suggestion_en"])
                self.assertEqual(classification.reason, conclusion["reason"])
                self.assertEqual("inactive" if key == "inactive" else status, conclusion["status"])
                self.assertEqual(key == "blocking", conclusion["blocking"])
                self.assertFalse(output["scan"]["scope"]["testsExecuted"])
                Draft202012Validator(SCHEMA).validate(output)
                self.assertEqual([], reference_errors(output))


class BilingualCliComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = {}
        for fixture in LEDGER["fixtures"]:
            temp = tempfile.TemporaryDirectory()
            cls.addClassCleanup(temp.cleanup)
            code = main(["scan", "--input", str(FIXTURES / fixture), "--rules", str(ROOT / "rulesets/riscv-porting"), "--output", temp.name])
            if code:
                raise AssertionError((fixture, code))
            cls.artifacts[fixture] = {name: (Path(temp.name) / name).read_bytes() for name in ("scan-result.json", "scan-report.html", "scan.log")}

    def test_new_reports_match_approved_field_differential_and_log_hashes(self):
        for fixture, artifacts in self.artifacts.items():
            with self.subTest(fixture=fixture):
                payload = json.loads(artifacts["scan-result.json"])
                Draft202012Validator(SCHEMA).validate(payload)
                self.assertEqual([], reference_errors(payload))
                expected = LEDGER["fixtures"][fixture]["2.0"]
                self.assertEqual(expected["after"], digest(payload))
                self.assertEqual(expected["logSha256"], hashlib.sha256(artifacts["scan.log"]).hexdigest())
                rendered = artifacts["scan-report.html"].decode("utf-8")
                for finding in payload["findings"]:
                    conclusion = finding["conclusion"]
                    pair = {"zh": conclusion.pop("suggestion"), "en": conclusion.pop("suggestion_en")}
                    self.assertIn(pair, PAIRS.values())
                    self.assertIn(html.escape(pair["zh"], quote=True), rendered)
                    self.assertNotIn(pair["en"], rendered)
                    if conclusion["status"] == "unknown":
                        self.assertEqual(PAIRS["unknown"], pair)
                    elif conclusion["status"] == "inactive":
                        self.assertEqual(PAIRS["inactive"], pair)
                    elif conclusion["findingType"] == "x86_comment_hint":
                        self.assertEqual(PAIRS["hint"], pair)
                    elif fixture == "rpm-architecture" and conclusion["findingType"] == "build_selected_x86_dependency":
                        self.assertFalse(conclusion["blocking"])
                        self.assertEqual(PAIRS["local"], pair)
                self.assertEqual(expected["strippedSha256"], digest(payload))

    def test_nondefault_locale_never_swaps_v2_language_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            code = main(["scan", "--input", str(FIXTURES / "architecture-enum"), "--rules", str(ROOT / "rulesets/riscv-porting"),
                         "--output", temp, "--locale", "en-US", "--schema-version", "2.0"])
            self.assertEqual(0, code)
            for name, content in self.artifacts["architecture-enum"].items():
                self.assertEqual(content, (Path(temp) / name).read_bytes())

    def test_usage_extension_does_not_change_reviewed_core_or_existing_extensions(self):
        namespace = "org.rvport.kb-scanner.candidate-usage"
        for fixture, artifacts in self.artifacts.items():
            with self.subTest(fixture=fixture):
                report = json.loads(artifacts["scan-result.json"])
                if namespace in report.get("extensions", {}):
                    audit = report["extensions"].pop(namespace)
                    self.assertEqual(0, audit["excludedCount"])
                    self.assertEqual([], audit["excludedCandidates"])
                    if not report["extensions"]:
                        del report["extensions"]
                for finding in report["findings"]:
                    extensions = finding["fact"].get("extensions", {})
                    usage = extensions.pop(namespace, None)
                    if usage is not None:
                        self.assertTrue(usage["roots"])
                        for root in usage["roots"]:
                            self.assertEqual("unknown", root["status"])
                            self.assertTrue(root["reasonCodes"])
                            self.assertTrue(root["explanation"])
                            self.assertTrue(root["explanation_en"])
                        if not extensions:
                            del finding["fact"]["extensions"]
                # 宏作用链有独立逐字段审校；其他样例仍精确重现历史摘要。
                reviewed_macro = MACRO_LEDGER['fixtures'].get(fixture,{}).get('2.0',{})
                expected = reviewed_macro.get('withoutCandidateUsageSha256',HISTORICAL_LEDGER["fixtures"][fixture]["2.0"]["after"])
                self.assertEqual(expected, digest(report))

    def test_compiler_facts_are_byte_identical_to_frozen_inputs(self):
        for name, expected in LEDGER["compilerFacts"].items():
            self.assertEqual(expected, hashlib.sha256((ROOT / "rulesets/riscv-porting/generated" / name).read_bytes()).hexdigest())
