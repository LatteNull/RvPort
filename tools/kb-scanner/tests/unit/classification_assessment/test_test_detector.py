from __future__ import annotations

import unittest

from kb_scanner.analyzers import TestAssetAnalyzer, TestSelectionAnalyzer
from kb_scanner.core import AnalysisSnapshot, CompletionStatus, Entity, ProofPath, Relation, stable_id
from kb_scanner.detectors import TestSelectionDetector
from tests.unit.classification_assessment.support import context, knowledge, test_facts


def _run(status: str, known: bool = True):
    facts = test_facts(status=status)
    kb = knowledge("-mavx") if known else knowledge()
    assets = TestAssetAnalyzer().analyze(context(), facts, kb).value
    analysis = TestSelectionAnalyzer().analyze(context(), facts, kb, assets).value
    return TestSelectionDetector().detect(context(), facts, analysis, kb)


class TestSelectionDetectorTests(unittest.TestCase):
    def test_complete_path_does_not_mask_unknown_required_path(self):
        from dataclasses import replace
        facts, kb = test_facts(), knowledge("-mavx")
        assets = TestAssetAnalyzer().analyze(context(), facts, kb).value
        analysis = TestSelectionAnalyzer().analyze(context(), facts, kb, assets).value
        exercise = next(r for r in analysis.relations if r.kind == "exercises")
        proof = next(p for p in analysis.proof_paths if exercise.id in p.relation_ids)
        unknown = replace(proof, id=stable_id("unknown-required-test-path"), status="unknown")
        changed = replace(analysis, proof_paths=(*analysis.proof_paths, unknown))
        result = TestSelectionDetector().detect(context(), facts, changed, kb)
        self.assertFalse(any(o.kind == "riscv_test_blocker" and exercise.id in o.relation_ids for o in result.value.observations))
        self.assertTrue(any(o.kind == "test_selection_unknown" and exercise.id in o.relation_ids for o in result.value.observations))

    def test_unrelated_entities_do_not_repeat_whole_proof_inventory(self):
        from types import SimpleNamespace
        facts, kb = test_facts(), knowledge('-mavx')
        assets = TestAssetAnalyzer().analyze(context(), facts, kb).value
        analysis = TestSelectionAnalyzer().analyze(context(), facts, kb, assets).value
        expected = TestSelectionDetector().detect(context(), facts, analysis, kb)
        class Counted(list):
            scans = 0
            def __iter__(self):
                self.scans += 1
                return super().__iter__()
        proofs = Counted(analysis.proof_paths)
        extra = tuple(Entity(stable_id('unrelated', number), 'usage_record', str(number)) for number in range(200))
        indexed = SimpleNamespace(relations=analysis.relations, entities=(*analysis.entities, *extra), proof_paths=proofs)
        actual = TestSelectionDetector().detect(context(), facts, indexed, kb)
        self.assertEqual(expected, actual)
        self.assertEqual(2, proofs.scans)  # 引用校验一次，按终点分组一次。

    def test_selected_and_inactive_x86_test_paths_are_distinguished(self) -> None:
        selected = _run("selected")
        self.assertEqual(selected.status, CompletionStatus.COMPLETE)
        blocker = next(item for item in selected.value.observations if item.kind == "riscv_test_blocker")
        self.assertEqual(blocker.status, "confirmed_local")
        self.assertTrue(blocker.relation_ids)
        self.assertTrue(blocker.knowledge_ids)
        self.assertTrue(blocker.metadata["proofPathIds"])
        self.assertNotIn("severity", blocker.metadata)
        inactive = _run("inactive")
        guarded = next(item for item in inactive.value.observations if item.kind == "x86_test_guarded")
        self.assertEqual(guarded.metadata["selectionStatus"], "inactive")

    def test_unknown_candidate_and_unknown_x86_shape_are_not_promoted(self) -> None:
        unknown = _run("unknown")
        self.assertEqual(unknown.status, CompletionStatus.PARTIAL)
        self.assertTrue(all(item.kind == "test_selection_unknown" for item in unknown.value.observations))
        no_knowledge = _run("selected", known=False)
        self.assertTrue(any(item.metadata["reason"] == "x86-shaped-test-dependency-without-knowledge" for item in no_knowledge.value.observations))

    def test_file_membership_does_not_duplicate_local_fact_as_test_blocker(self) -> None:
        from kb_scanner.core import Evidence, NormalizedFact, NormalizedSnapshot

        facts = test_facts(include_x86=False)
        source = facts.entities[1]
        evidence = Evidence(stable_id("local-test-x86"), "call", source.id, "_mm_pause", "unit", "syntax", "high")
        fact = NormalizedFact(stable_id("local-test-x86-fact"), "call", source.id, "_mm_pause", "source:test:1", (evidence.id,))
        enriched = NormalizedSnapshot(facts.entities, (*facts.evidence, evidence), (*facts.facts, fact))
        kb = knowledge("_mm_pause")
        assets = TestAssetAnalyzer().analyze(context(), enriched, kb).value
        analysis = TestSelectionAnalyzer().analyze(context(), enriched, kb, assets).value
        result = TestSelectionDetector().detect(context(), enriched, analysis, kb)
        self.assertFalse(any(item.kind == "riscv_test_blocker" for item in result.value.observations))
        self.assertIn(evidence, enriched.evidence)
        self.assertIn(fact, enriched.facts)

    def test_complete_inventory_produces_gap_but_incomplete_inventory_is_unknown(self) -> None:
        facts = test_facts(include_x86=False)
        complete = Entity(stable_id("impl-complete"), "source_file", "src/rv.c", properties={"coverageRequired": True, "testInventoryComplete": True})
        complete_two = Entity(stable_id("impl-complete-two"), "source_file", "src/rv-extra.c", properties={"coverageRequired": True, "testInventoryComplete": True})
        incomplete = Entity(stable_id("impl-incomplete"), "source_file", "src/rv2.c", properties={"coverageRequired": True})
        assets = TestAssetAnalyzer().analyze(context(), facts, knowledge()).value
        selected = TestSelectionAnalyzer().analyze(context(), facts, knowledge(), assets).value
        analysis = AnalysisSnapshot(selected.relations, (*selected.entities, complete, complete_two, incomplete), selected.proof_paths)
        result = TestSelectionDetector().detect(context(), facts, analysis, knowledge())
        kinds = {item.kind for item in result.value.observations}
        self.assertEqual(kinds, {"riscv_test_coverage_gap", "test_selection_unknown"})
        self.assertEqual(sum(item.kind == "riscv_test_coverage_gap" for item in result.value.observations), 2)
        gap = next(item for item in result.value.observations if item.kind == "riscv_test_coverage_gap")
        self.assertTrue(gap.relation_ids)
        self.assertNotIn("readiness", gap.metadata)

    def test_explicit_coverage_suppresses_gap(self) -> None:
        facts = test_facts(include_x86=False)
        implementation = Entity(stable_id("impl"), "source_file", "src/rv.c", properties={"coverageRequired": True, "testInventoryComplete": True})
        target = Entity(stable_id("test-target"), "test_target", "unit-test")
        relation = Relation(stable_id("coverage"), "covers_candidate", target.id, implementation.id, (facts.evidence[0].id,), "high", "selected")
        result = TestSelectionDetector().detect(context(), facts, AnalysisSnapshot((relation,), (*facts.entities, implementation, target)), knowledge())
        self.assertEqual(result.value.observations, ())

    def test_invalid_relation_proof_and_knowledge_references_fail(self) -> None:
        facts = test_facts()
        bad_relation = Relation(stable_id("bad"), "exercises", stable_id("missing"), facts.entities[0].id, (facts.evidence[0].id,))
        self.assertEqual(TestSelectionDetector().detect(context(), facts, AnalysisSnapshot((bad_relation,), facts.entities), knowledge()).status, CompletionStatus.FAILED)
        good_relation = Relation(stable_id("good"), "exercises", facts.entities[0].id, facts.entities[1].id, (facts.evidence[0].id,))
        bad_proof = ProofPath(stable_id("proof"), facts.entities[0].id, facts.entities[1].id, (stable_id("missing-relation"),), "unknown", "missing")
        self.assertEqual(TestSelectionDetector().detect(context(), facts, AnalysisSnapshot((good_relation,), facts.entities, (bad_proof,)), knowledge()).status, CompletionStatus.FAILED)
        relation = Relation(
            stable_id("unknown-kb"), "exercises", facts.entities[0].id, facts.entities[1].id,
            (facts.evidence[0].id,), "high", "selected", {"knowledgeIds": (stable_id("unknown-kb-entry"),)},
        )
        proof = ProofPath(stable_id("valid-proof"), facts.entities[0].id, facts.entities[1].id, (relation.id,), "complete", visited=2)
        self.assertEqual(TestSelectionDetector().detect(context(), facts, AnalysisSnapshot((relation,), facts.entities, (proof,)), knowledge()).status, CompletionStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
