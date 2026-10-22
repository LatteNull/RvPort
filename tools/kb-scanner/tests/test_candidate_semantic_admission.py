"""Real-parser/report regression, deliberately separate from isolated coverage."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from kb_scanner.normalization import CppEvidenceNormalizer
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.core import AnalysisSnapshot, FrontendSnapshot
from tests.unit.knowledge_detection.support import make_context
from tests.unit.knowledge_detection.test_local_matchers import knowledge

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/candidate-semantic-admission"


class CandidateSemanticRegressionTests(unittest.TestCase):
    def test_default_and_explicit_v2_and_v1_preserve_unresolved_facts(self):
        payloads = []
        for version in (None, "2.0", "1.0"):
            with tempfile.TemporaryDirectory() as output:
                result = create_default_application().run(ScanRequest(str(FIXTURE), str(ROOT / "rulesets/riscv-porting"), output, **({"schema_version": version} if version else {})))
                self.assertEqual(0, result.exit_code)
                self.assertEqual(["scan-result.json", "scan-report.html", "scan.log"], [a.name for a in result.artifacts])
                payloads.append(json.loads((Path(output) / "scan-result.json").read_text()))
        # Root-independent outputs have no timing/random data; output paths are not IDs.
        self.assertEqual(payloads[0], payloads[1])
        candidates = [f for f in payloads[0]["findings"] if f["conclusion"]["findingType"] in {"architecture_enum_candidate", "architecture_identifier_candidate"}]
        symbols = {f["fact"]["symbol"] for f in candidates}
        for fragment in ("avx2", "CKSUM_SHA512", "CRC32", "_7Z_X86", "BOOT_PLATFORM_X86", "MY_X86_MODE"):
            self.assertTrue(any(fragment in symbol for symbol in symbols), fragment)
        self.assertFalse(any(f["fact"]["symbol"] == "defined(__i386__)" for f in candidates))
        for finding in candidates:
            if finding["conclusion"]["archReachability"] != "inactive":
                self.assertEqual("unknown", finding["conclusion"]["status"])
                self.assertFalse(finding["conclusion"]["blocking"])
                self.assertFalse(finding["conclusion"]["actionable"])
                self.assertEqual("unknown", finding["evidenceChain"]["status"])
                self.assertIn("当前证据不足", finding["conclusion"]["suggestion"])
                self.assertIn("cannot be determined", finding["conclusion"]["suggestion_en"])
        calls = [s for f in candidates for s in f["evidenceChain"]["steps"] if s.get("symbol") == "archive_sha512_update"]
        self.assertTrue(calls)
        self.assertTrue(all(s["kind"] == "source_evidence" for s in calls))
        self.assertTrue(any("avx2" in str(f.get("symbol")) for f in payloads[2]["findings"]))
        self.assertFalse(any(d["code"] == "classifier.candidate-semantic-exclusions" for d in payloads[0]["diagnostics"]))

    def test_detection_does_not_remove_frontend_or_normalized_facts(self):
        entity = make_source_file_entity("candidates.cpp", ("cpp",), "1")
        context = make_context(FIXTURE)
        parsed = TreeSitterCppAdapter().analyze_file(context, FIXTURE, entity.name, entity)
        self.assertIsNotNone(parsed.value)
        snapshot = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), parsed.value)).value
        before = snapshot.facts, snapshot.evidence, snapshot.entities
        LocalX86Detector().detect(context, snapshot, AnalysisSnapshot(), knowledge())
        self.assertEqual(before, (snapshot.facts, snapshot.evidence, snapshot.entities))
        self.assertTrue(any(f.canonical_value == "_7Z_X86" for f in snapshot.facts))
        self.assertTrue(any("CKSUM_SHA512" in f.canonical_value for f in snapshot.facts))

    def test_audit_inventory_and_original_compiler_facts(self):
        audit = json.loads((FIXTURE / "libarchive-review.json").read_text())
        self.assertEqual(55, len(audit["findings"]))
        self.assertEqual(55, len({f["id"] for f in audit["findings"]}))
        self.assertEqual(26, audit["counts"]["candidate_to_review"])
        reviewed = [f for f in audit["findings"] if f["review"]["group"] == "candidate_to_review"]
        self.assertTrue(all(f["review"]["implementationStatus"] == "retained_unknown" for f in reviewed))
        self.assertEqual(1, sum(f["review"]["implementationStatus"] == "deduplicated_same_fact" for f in audit["findings"]))
        for name, expected in (("clang-x86-entries.json", "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7"),
                               ("gcc-x86-entries.json", "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191")):
            self.assertEqual(expected, hashlib.sha256((ROOT / "rulesets/riscv-porting/generated" / name).read_bytes()).hexdigest())
