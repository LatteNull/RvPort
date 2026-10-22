from __future__ import annotations

import unittest
from dataclasses import replace

from kb_scanner.classifiers import ClassificationPolicy, MigrationClassifier
from kb_scanner.core import (
    AnalysisSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Observation,
    ProofPath,
    stable_id,
)
from tests.unit.classification_assessment.support import context, proof_analysis


class ClassifierTests(unittest.TestCase):
    def test_inferred_proof_index_preserves_all_and_only_intersecting_paths(self):
        analysis, observation = proof_analysis(status='selected')
        first = analysis.proof_paths[0]
        second = replace(first, id=stable_id('second-proof'))
        unrelated = replace(first, id=stable_id('unrelated-proof'), relation_ids=(stable_id('unrelated-relation'),))
        observation = replace(observation, metadata={**observation.metadata, 'proofPathIds': ()})
        expanded = replace(analysis, proof_paths=(unrelated, second, first))
        result = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), expanded)
        self.assertEqual(CompletionStatus.COMPLETE, result.status)
        self.assertEqual(tuple(sorted((first.id, second.id))), result.value.classifications[0].proof_path_ids)
        self.assertEqual('blocking_issue', result.value.classifications[0].impact)

    def test_policy_validation_and_all_decision_classes(self) -> None:
        with self.assertRaises(ValueError):
            ClassificationPolicy("", 1)
        with self.assertRaises(ValueError):
            ClassificationPolicy("p", 0)
        policy = ClassificationPolicy("p", 1)
        cases = (
            (Observation(stable_id("o1"), "d", "test_selection_unknown"), True, False, "unknown"),
            (Observation(stable_id("o2"), "d", "riscv_test_blocker"), False, False, "unknown"),
            (Observation(stable_id("o3"), "d", "riscv_test_blocker"), True, False, "blocking_issue"),
            (Observation(stable_id("o4"), "d", "x86_test_guarded"), False, False, "unknown"),
            (Observation(stable_id("o5"), "d", "x86_test_guarded"), True, False, "guarded_inactive"),
            (Observation(stable_id("o6"), "d", "riscv_test_coverage_gap"), False, False, "actionable_non_blocking"),
            (Observation(stable_id("o7"), "d", "anything", status="hint"), False, False, "hint"),
            (Observation(stable_id("o8"), "d", "anything", status="confirmed_local"), False, False, "actionable_non_blocking"),
            (Observation(stable_id("o9"), "d", "anything"), False, False, "unknown"),
            (Observation(stable_id("o10"), "d", "anything", metadata={"basis": "comment-token"}), False, False, "hint"),
        )
        for observation, complete, relation_unknown, expected in cases:
            with self.subTest(observation=observation.id):
                self.assertEqual(policy.decide(observation, proof_complete=complete, relation_unknown=relation_unknown).impact, expected)
        relation_unknown = policy.decide(cases[2][0], proof_complete=True, relation_unknown=True)
        self.assertEqual(relation_unknown.impact, "unknown")
        guarded = replace(cases[2][0], metadata={"branchRole": "x86"})
        self.assertEqual(policy.decide(guarded, proof_complete=False, relation_unknown=True).impact, "unknown")
        self.assertEqual(policy.decide(guarded, proof_complete=True, relation_unknown=False).impact, "guarded_inactive")

    def test_selected_guarded_actionable_hint_and_unknown_classifications(self) -> None:
        selected_analysis, selected = proof_analysis(status="selected")
        selected_result = MigrationClassifier().classify(context(), DetectionSnapshot((selected,)), selected_analysis)
        self.assertEqual(selected_result.value.classifications[0].impact, "blocking_issue")
        self.assertEqual(selected_result.value.observations, (selected,))
        inactive_analysis, inactive = proof_analysis(status="inactive")
        self.assertEqual(MigrationClassifier().classify(context(), DetectionSnapshot((inactive,)), inactive_analysis).value.classifications[0].impact, "guarded_inactive")
        local = Observation(stable_id("local"), "LOCAL", "x86_intrinsic", status="confirmed_local", confidence="high", metadata={"factId": stable_id("fact")})
        hint = Observation(stable_id("hint"), "LOCAL", "comment", status="hint", confidence="low")
        unknown = Observation(stable_id("candidate"), "LOCAL", "candidate", confidence="medium")
        result = MigrationClassifier().classify(context(), DetectionSnapshot((unknown, hint, local)), AnalysisSnapshot())
        self.assertEqual({item.impact for item in result.value.classifications}, {"actionable_non_blocking", "hint", "unknown"})
        self.assertEqual(result.status, CompletionStatus.PARTIAL)

    def test_incomplete_proof_and_unknown_relation_win_over_blocking_rule(self) -> None:
        analysis, observation = proof_analysis(status="selected")
        incomplete = ProofPath(
            analysis.proof_paths[0].id,
            analysis.proof_paths[0].source_id,
            analysis.proof_paths[0].target_id,
            analysis.proof_paths[0].relation_ids,
            "unknown",
            "truncated",
            2,
            True,
        )
        result = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), AnalysisSnapshot(analysis.relations, analysis.entities, (incomplete,)))
        self.assertEqual(result.value.classifications[0].impact, "unknown")

    def test_same_root_merges_provenance_but_configuration_stays_separate(self) -> None:
        analysis, first = proof_analysis(status="selected")
        second = Observation(
            stable_id("second"), first.detector_id, first.kind,
            (stable_id("second-evidence"),), first.relation_ids, "medium", first.status,
            {**dict(first.metadata), "producer": "two"}, first.knowledge_ids,
        )
        merged = MigrationClassifier().classify(context(), DetectionSnapshot((second, first)), analysis).value.classifications
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0].observation_ids), {first.id, second.id})
        self.assertEqual(merged[0].confidence, "medium")
        third = Observation(
            stable_id("third"), first.detector_id, first.kind, first.evidence_ids,
            first.relation_ids, "high", first.status,
            {**dict(first.metadata), "configuration": "other"}, first.knowledge_ids,
        )
        separate = MigrationClassifier().classify(context(), DetectionSnapshot((first, third)), analysis).value.classifications
        self.assertEqual(len(separate), 2)
        reverse = MigrationClassifier().classify(context(), DetectionSnapshot((third, first)), analysis).value.classifications
        self.assertEqual(separate, reverse)

    def test_invalid_relation_and_proof_references_fail(self) -> None:
        invalid_relation = Observation(stable_id("bad-r"), "d", "candidate", relation_ids=(stable_id("missing"),))
        result = MigrationClassifier().classify(context(), DetectionSnapshot((invalid_relation,)), AnalysisSnapshot())
        self.assertEqual(result.status, CompletionStatus.FAILED)
        invalid_proof = Observation(stable_id("bad-p"), "d", "candidate", metadata={"proofPathIds": (stable_id("missing"),)})
        result = MigrationClassifier().classify(context(), DetectionSnapshot((invalid_proof,)), AnalysisSnapshot())
        self.assertEqual(result.status, CompletionStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
