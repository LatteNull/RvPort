from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
from kb_scanner.core import Observation, ScanRequest, stable_id
from kb_scanner.detectors.definitions import DEFAULT_DEFINITIONS
from kb_scanner.detectors.matchers import KnowledgeIndex, _identifier_components, match_fact
from kb_scanner.frontends.cpp.clang_adapter import _cursor_kind, _enum_cursor_metadata
from kb_scanner.frontends.cpp.tree_sitter_adapter import TreeSitterCppAdapter
from kb_scanner.frontends.cpp.vocabulary import CPP_EVIDENCE_KINDS, make_source_file_entity
from kb_scanner.normalization import CppEvidenceNormalizer
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.projection.policy import DEFAULT_PROJECTION_POLICY
from tests.unit.knowledge_detection.support import make_context
from tests.unit.knowledge_detection.test_local_matchers import fact, knowledge


ROOT = Path(__file__).resolve().parents[3]
RULES = ROOT / "rulesets/riscv-porting"
CONSTEXPR = ROOT / "tests/fixtures/riscv-porting/cpp_x86_constexpr_arch_branch/src"
MATRIX = ROOT / "tests/fixtures/architecture-enum"


class ArchitectureEnumFrontendTests(unittest.TestCase):
    def test_tree_sitter_extracts_bounded_enum_evidence_and_precise_condition(self) -> None:
        entity = make_source_file_entity("matrix.cpp", ("cpp",), "1")
        result = TreeSitterCppAdapter().analyze_file(make_context(MATRIX), MATRIX, "matrix.cpp", entity)
        self.assertIsNotNone(result.value)
        evidence = result.value
        kinds = {item.kind for item in evidence}
        self.assertTrue({"enum_declaration", "enum_member_declaration", "enum_member_reference", "constexpr_condition", "selection_condition"}.issubset(kinds))
        avx_refs = [item for item in evidence if item.kind == "enum_member_reference" and item.metadata.get("memberName") in {"avx2", "BACKEND_AVX2"}]
        self.assertGreaterEqual(len(avx_refs), 4)
        self.assertTrue(all(item.metadata["enumMemberDeclarationEvidenceIds"] for item in avx_refs))
        constexpr = next(item for item in evidence if item.kind == "constexpr_condition" and item.metadata.get("selectionContext") == "if_constexpr")
        self.assertEqual(15, constexpr.location.start.line)
        self.assertEqual("(B == Backend::avx2)", constexpr.value)
        reference_ids = {item.id for item in evidence if item.kind == "enum_member_reference"}
        self.assertTrue(constexpr.metadata["enumMemberReferenceEvidenceIds"])
        self.assertTrue(set(constexpr.metadata["enumMemberReferenceEvidenceIds"]).issubset(reference_ids))
        self.assertNotIn("identifier", CPP_EVIDENCE_KINDS)

        normalized = CppEvidenceNormalizer().normalize(make_context(MATRIX), SimpleNamespace(entities=(entity,), evidence=evidence))
        self.assertIsNotNone(normalized.value)
        self.assertFalse(any(item.code == "normalization.unsupported-evidence-kind" and "constexpr" in item.message for item in normalized.diagnostics))
        self.assertTrue({"enum_declaration", "enum_member", "enum_reference", "selection_condition"}.issubset({item.kind for item in normalized.value.facts}))

    def test_negative_file_does_not_emit_unbound_identifier_references(self) -> None:
        entity = make_source_file_entity("negative.cpp", ("cpp",), "1")
        result = TreeSitterCppAdapter().analyze_file(make_context(MATRIX), MATRIX, "negative.cpp", entity)
        references = [item for item in result.value if item.kind == "enum_member_reference"]
        self.assertEqual([], references)

    def test_clang_cursor_contract_tracks_semantic_enum_binding(self) -> None:
        enum_kind = SimpleNamespace(name="ENUM_DECL")
        member_kind = SimpleNamespace(name="ENUM_CONSTANT_DECL")
        enum_cursor = SimpleNamespace(kind=enum_kind, spelling="Backend", get_usr=lambda: "enum:Backend")
        declaration = SimpleNamespace(id=stable_id("decl"))
        member_cursor = SimpleNamespace(kind=member_kind, spelling="avx2", semantic_parent=enum_cursor, get_usr=lambda: "member:avx2")
        decl_meta = _enum_cursor_metadata(enum_cursor, "enum_declaration", {}, {}, False)
        member_meta = _enum_cursor_metadata(member_cursor, "enum_member_declaration", {"enum:Backend": declaration}, {}, False)
        reference = SimpleNamespace(kind=SimpleNamespace(name="DECL_REF_EXPR"), spelling="avx2", referenced=member_cursor)
        member_evidence = SimpleNamespace(id=stable_id("member"))
        ref_meta = _enum_cursor_metadata(reference, "enum_member_reference", {}, {"member:avx2": member_evidence}, False)
        self.assertEqual("enum_declaration", _cursor_kind(enum_cursor))
        self.assertEqual("enum_member_reference", _cursor_kind(reference))
        self.assertEqual("Backend", decl_meta["enumName"])
        self.assertEqual(declaration.id, member_meta["enumDeclarationEvidenceId"])
        self.assertEqual((member_evidence.id,), ref_meta["enumMemberDeclarationEvidenceIds"])


class ArchitectureEnumDetectionPolicyTests(unittest.TestCase):
    def test_identifier_components_and_fact_backed_candidates_are_bounded(self) -> None:
        definition = DEFAULT_DEFINITIONS["C_CPP.X86.ARCH_ENUM_REFERENCE_CANDIDATE"]
        index = KnowledgeIndex(knowledge())
        for value in ("Backend::avx2", "BACKEND_AVX2", "backendAvx2"):
            result = match_fact(definition, fact("enum_reference", value), index)
            self.assertIsNotNone(result)
            self.assertEqual("candidate", result.status)
            self.assertTrue(result.knowledge_ids)
        self.assertIn("avx2", _identifier_components("Backend::BACKEND_AVX2"))
        self.assertIsNone(match_fact(definition, fact("enum_reference", "avx2_counted"), index))
        self.assertIsNone(match_fact(definition, fact("enum_reference", "portable"), index))

    def test_classifier_is_conservative_until_relation_is_complete(self) -> None:
        base = dict(
            id=stable_id("enum-observation"), detector_id="C_CPP.X86.ARCH_ENUM_REFERENCE_CANDIDATE",
            kind="architecture_enum_candidate", evidence_ids=(stable_id("evidence"),), confidence="medium",
            status="candidate",
        )
        isolated = Observation(**base, metadata={"bindingStatus": "complete"})
        dependent = Observation(**base, metadata={"bindingStatus": "complete", "templateDependent": True})
        complete = Observation(**base, metadata={"bindingStatus": "complete", "enumDependencyComplete": True})
        selected = Observation(**base, metadata={"bindingStatus": "complete", "enumSelectionStatus": "selected"})
        self.assertEqual("unknown", DEFAULT_CLASSIFICATION_POLICY.decide(isolated, proof_complete=False, relation_unknown=False).impact)
        self.assertEqual("unknown", DEFAULT_CLASSIFICATION_POLICY.decide(dependent, proof_complete=False, relation_unknown=True).impact)
        self.assertEqual("actionable_non_blocking", DEFAULT_CLASSIFICATION_POLICY.decide(complete, proof_complete=True, relation_unknown=False).impact)
        self.assertEqual("blocking_issue", DEFAULT_CLASSIFICATION_POLICY.decide(selected, proof_complete=True, relation_unknown=False).impact)

    def test_v1_policy_uses_legacy_constexpr_identity(self) -> None:
        observation = SimpleNamespace(detector_id="C_CPP.X86.ARCH_ENUM_REFERENCE_CANDIDATE", kind="architecture_enum_candidate", metadata={"selectionContext": "if_constexpr"})
        classification = SimpleNamespace(reason="unit", impact="unknown", metadata={})
        self.assertEqual("CPP.X86.CONSTEXPR_ARCH_BRANCH", DEFAULT_PROJECTION_POLICY.present(observation, classification).rule_id)
        observation.metadata = {}
        self.assertEqual("C_CPP.X86.ARCH_ENUM_CANDIDATE", DEFAULT_PROJECTION_POLICY.present(observation, classification).rule_id)
        self.assertEqual((), DEFAULT_PROJECTION_POLICY.validate_completeness())


class ArchitectureEnumProjectionTests(unittest.TestCase):
    def _scan(self, version: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as output:
            result = create_default_application().run(ScanRequest(str(CONSTEXPR), str(RULES), output, schema_version=version))
            self.assertEqual(0, result.exit_code, result.diagnostics)
            return json.loads((Path(output) / "scan-result.json").read_text(encoding="utf-8"))

    def test_default_v2_is_self_contained_and_uses_existing_core_vocabulary(self) -> None:
        payload = self._scan("2.0")
        self.assertEqual(1, payload["summary"]["findings"])
        finding = payload["findings"][0]
        self.assertEqual("architecture_probe", finding["fact"]["kind"])
        self.assertEqual("enum_member_reference", finding["fact"]["extensions"]["org.rvport.kb-scanner.architecture-enum"]["evidenceKind"])
        self.assertEqual(8, finding["fact"]["primaryLocation"]["span"]["start"]["line"])
        self.assertIn(finding["primaryOccurrenceId"], {item["id"] for item in finding["occurrences"]})
        enum_steps = [item for item in finding["evidenceChain"]["steps"] if item.get("extensions") and "org.rvport.kb-scanner.architecture-enum" in item["extensions"]]
        self.assertTrue(enum_steps)
        self.assertTrue(all(item.get("source", {}).get("context", {}).get("lines") for item in enum_steps))

    def test_explicit_v1_preserves_constexpr_rule_and_schema(self) -> None:
        payload = self._scan("1.0")
        self.assertEqual("1.0", payload["schemaVersion"])
        self.assertEqual(1, payload["summary"]["findings"])
        self.assertEqual("CPP.X86.CONSTEXPR_ARCH_BRANCH", payload["findings"][0]["rule_id"])
        self.assertEqual("avx2", payload["findings"][0]["symbol"])


if __name__ == "__main__":
    unittest.main()
