from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_scanner.core import (
    AnalysisSnapshot,
    CompletionStatus,
    Entity,
    FrontendSnapshot,
    KnowledgeEntry,
    KnowledgeSnapshot,
    KnowledgeSource,
    NormalizedFact,
    NormalizedSnapshot,
    ProofPath,
    Relation,
    stable_id,
)
from kb_scanner.detectors import LocalX86Detector
from kb_scanner.detectors.definitions import DEFAULT_DEFINITIONS
from kb_scanner.detectors.matchers import MatchResult
from tests.unit.knowledge_detection.support import make_context, make_entity, make_evidence


def inputs(value: str = "immintrin.h") -> tuple[NormalizedSnapshot, KnowledgeSnapshot]:
    entity = make_entity()
    evidence = make_evidence(entity, "include", value)
    fact = NormalizedFact(stable_id("fact", value), "include", entity.id, value, "scope", (evidence.id,), producers=(evidence.producer,))
    source = KnowledgeSource(stable_id("source"), "clang", "generated-json", "facts.json", "a" * 64)
    entry = KnowledgeEntry(stable_id("entry", value), "headers", "x86", value, (source.id,))
    return NormalizedSnapshot((entity,), (evidence,), (fact,)), KnowledgeSnapshot(stable_id("knowledge"), "1", (source,), (entry,))


class LocalDetectorTests(unittest.TestCase):
    def test_confirmed_observation_has_evidence_and_knowledge_without_classification(self) -> None:
        facts, knowledge = inputs()
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={}).detect(make_context(Path(tmp)), facts, AnalysisSnapshot(), knowledge)
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual(len(result.value.observations), 1)
        observation = result.value.observations[0]
        self.assertEqual(observation.status, "confirmed_local")
        self.assertTrue(observation.evidence_ids)
        self.assertTrue(observation.knowledge_ids)
        self.assertNotIn("severity", observation.metadata)
        self.assertNotIn("blocking", observation.metadata)

    def test_deferred_capabilities_make_partial_without_removing_observations(self) -> None:
        facts, knowledge = inputs()
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={"asm": "needs-curated-knowledge"}).detect(
                make_context(Path(tmp)), facts, AnalysisSnapshot(), knowledge
            )
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertTrue(result.value.observations)
        self.assertEqual(result.diagnostics[0].details["capabilities"][0]["reason"], "needs-curated-knowledge")

    def test_structural_candidate_is_allowed_without_fake_knowledge(self) -> None:
        entity = make_entity()
        evidence = make_evidence(entity, "inline_asm", "asm(pause)")
        fact = NormalizedFact(stable_id("fact"), "inline_asm", entity.id, "asm(pause)", "scope", (evidence.id,))
        facts = NormalizedSnapshot((entity,), (evidence,), (fact,))
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={}).detect(
                make_context(Path(tmp)), facts, AnalysisSnapshot(), KnowledgeSnapshot(stable_id("k"), "1")
            )
        item = result.value.observations[0]
        self.assertEqual(item.status, "candidate")
        self.assertEqual(item.knowledge_ids, ())

    def test_invalid_fact_or_matcher_knowledge_reference_fails(self) -> None:
        facts, knowledge = inputs()
        invalid_fact = NormalizedSnapshot(facts.entities, (), facts.facts)
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            invalid = LocalX86Detector(deferred_capabilities={}).detect(context, invalid_fact, AnalysisSnapshot(), knowledge)
            with patch("kb_scanner.detectors.local.match_fact", return_value=MatchResult((stable_id("missing"),), "confirmed_local", "fake")):
                invalid_knowledge = LocalX86Detector(definitions={"x": next(iter(DEFAULT_DEFINITIONS.values()))}, deferred_capabilities={}).detect(
                    context, facts, AnalysisSnapshot(), knowledge
                )
        self.assertEqual(invalid.status, CompletionStatus.FAILED)
        self.assertEqual(invalid_knowledge.diagnostics[0].code, "detector.invalid-knowledge-reference")

    def test_input_order_does_not_change_observation_identity(self) -> None:
        facts, knowledge = inputs()
        repeated = NormalizedSnapshot(tuple(reversed(facts.entities)), tuple(reversed(facts.evidence)), tuple(reversed(facts.facts)))
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            first = LocalX86Detector(deferred_capabilities={}).detect(context, facts, AnalysisSnapshot(), knowledge)
            second = LocalX86Detector(deferred_capabilities={}).detect(context, repeated, AnalysisSnapshot(), knowledge)
        self.assertEqual(first, second)

    def test_knowledge_backed_asm_is_confirmed_while_vector_width_remains_candidate(self) -> None:
        entity = make_entity()
        asm_evidence = make_evidence(entity, "inline_asm", 'asm("pause %rax")')
        vector_evidence = make_evidence(entity, "declaration_attribute", "__attribute__((vector_size(16)))", line=2)
        facts = NormalizedSnapshot(
            (entity,), (asm_evidence, vector_evidence),
            (
                NormalizedFact(stable_id("asm-fact"), "inline_asm", entity.id, 'asm("pause %rax")', "scope", (asm_evidence.id,)),
                NormalizedFact(
                    stable_id("vector-fact"), "declaration_attribute", entity.id, "__attribute__((vector_size(16)))",
                    "scope-2", (vector_evidence.id,),
                ),
            ),
        )
        source = KnowledgeSource(stable_id("source", "new"), "new", "generated-json-v2", "new.json", "b" * 64)
        entries = tuple(
            KnowledgeEntry(stable_id("entry", kind), kind, "x86", value, (source.id,))
            for kind, value in (
                ("assemblyInstructions", "pause"), ("registerNames", "rax"), ("vectorWidthMarkers", "vector_size(16)"),
            )
        )
        knowledge = KnowledgeSnapshot(stable_id("knowledge", "new"), "2", (source,), entries)
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={}).detect(
                make_context(Path(tmp)), facts, AnalysisSnapshot(), knowledge,
            )
        statuses = {(item.kind, item.status) for item in result.value.observations}
        self.assertIn(("x86_assembly_instruction", "confirmed_local"), statuses)
        self.assertIn(("x86_register_reference", "confirmed_local"), statuses)
        self.assertIn(("fixed_vector_width_candidate", "candidate"), statuses)

    def test_graph_relations_and_proofs_are_attached_without_classification(self) -> None:
        facts, knowledge = inputs()
        source = facts.entities[0]
        target = make_entity("target.h")
        relation = Relation(
            stable_id("relation"), "includes", source.id, target.id, facts.facts[0].evidence_ids,
            status="partial", metadata={"reason": "ambiguous"},
        )
        proof = ProofPath(
            stable_id("proof"), source.id, target.id, (relation.id,), "partial", "ambiguous", 2
        )
        analysis = AnalysisSnapshot((relation,), (source, target), (proof,))
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={}).detect(make_context(Path(tmp)), facts, analysis, knowledge)
        observation = result.value.observations[0]
        self.assertEqual(observation.relation_ids, (relation.id,))
        self.assertEqual(observation.metadata["proofPathIds"], (proof.id,))
        self.assertEqual(observation.metadata["relationCompleteness"], ("partial",))
        self.assertNotIn("blocking", observation.metadata)
        self.assertNotIn("severity", observation.metadata)

    def test_x86_branch_and_compatible_sibling_metadata_are_attached(self) -> None:
        facts, knowledge = inputs()
        source = facts.entities[0]
        branch = Entity(stable_id("branch"), "branch", "if:defined(__x86_64__)")
        riscv = Entity(stable_id("riscv"), "branch", "elif:defined(__riscv)")
        implementation = Entity(stable_id("impl"), "implementation", "x86", properties={"role": "x86"})
        guarded = Relation(stable_id("guarded"), "guarded_by", source.id, branch.id, facts.facts[0].evidence_ids, status="complete")
        role = Relation(stable_id("role"), "guarded_by", implementation.id, branch.id, facts.facts[0].evidence_ids, status="complete")
        alternative = Relation(stable_id("alternative"), "alternative_to", branch.id, riscv.id, facts.facts[0].evidence_ids, status="complete", metadata={"sourceRole": "x86", "targetRole": "riscv"})
        analysis = AnalysisSnapshot((guarded, role, alternative), (source, branch, riscv, implementation), ())
        with tempfile.TemporaryDirectory() as tmp:
            result = LocalX86Detector(deferred_capabilities={}).detect(make_context(Path(tmp)), facts, analysis, knowledge)
        metadata = result.value.observations[0].metadata
        self.assertEqual("x86", metadata["branchRole"])
        self.assertEqual("riscv", metadata["compatibleBranchKind"])
        self.assertTrue(metadata["compatibleSiblingBranch"])
        self.assertEqual("defined(__x86_64__)", metadata["conditionExpression"])

    def test_invalid_relation_and_proof_references_fail(self) -> None:
        facts, knowledge = inputs()
        source = facts.entities[0]
        missing = make_entity("missing.h")
        invalid_relation = Relation(stable_id("r"), "includes", source.id, missing.id, facts.facts[0].evidence_ids)
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            relation_result = LocalX86Detector(deferred_capabilities={}).detect(
                context, facts, AnalysisSnapshot((invalid_relation,), (source,), ()), knowledge
            )
            valid_relation = Relation(stable_id("valid-r"), "includes", source.id, missing.id, facts.facts[0].evidence_ids)
            invalid_proof = ProofPath(stable_id("p"), source.id, missing.id, (stable_id("unknown-r"),), "unknown")
            proof_result = LocalX86Detector(deferred_capabilities={}).detect(
                context, facts, AnalysisSnapshot((valid_relation,), (source, missing), (invalid_proof,)), knowledge
            )
        self.assertEqual(relation_result.diagnostics[0].code, "detector.invalid-relation-reference")
        self.assertEqual(proof_result.diagnostics[0].code, "detector.invalid-proof-reference")


if __name__ == "__main__":
    unittest.main()
