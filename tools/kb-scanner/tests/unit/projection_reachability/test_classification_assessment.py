from __future__ import annotations

import unittest

from kb_scanner.assessors import MigrationAssessor
from kb_scanner.classifiers import MigrationClassifier
from kb_scanner.core import (
    AnalysisSnapshot, DetectionSnapshot, Entity, Observation, ProofPath, Relation, stable_id,
)
from kb_scanner.projection.policy import ProjectionPolicy
from tests.unit.classification_assessment.support import context


def selected_fixture(status: str = "selected"):
    selector = Entity(stable_id("selector"), "architecture_selector", "riscv64")
    source = Entity(stable_id("source"), "source_file", "foo.c")
    dependency = Entity(stable_id("dependency"), "architecture_dependency", "_mm_add_ps")
    evidence_id = stable_id("evidence")
    relation = Relation(
        stable_id("relation", status), "depends_on", source.id, dependency.id, (evidence_id,), "high", status,
        {"itemKind": "source_x86_dependency", "configuration": "cfg", "role": "x86"},
    )
    proof_status = "complete" if status in {"selected", "inactive", "not_selected"} else "unknown"
    proof = ProofPath(stable_id("proof", status), selector.id, dependency.id, (relation.id,), proof_status, None if proof_status == "complete" else "unknown", 2)
    observation = Observation(
        stable_id("observation", status), "C_CPP.X86.INTRINSIC", "x86_intrinsic_reference",
        (evidence_id,), (relation.id,), "high", "confirmed_local",
        {"proofPathIds": (proof.id,), "factId": "root", "configuration": "cfg"},
    )
    return AnalysisSnapshot((relation,), (selector, source, dependency), (proof,)), observation


class ClassificationAssessmentTests(unittest.TestCase):
    def test_selected_local_dependency_is_blocking_gap_and_x86_only(self) -> None:
        analysis, observation = selected_fixture()
        result = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), analysis)
        classification = result.value.classifications[0]
        self.assertEqual("blocking_issue", classification.impact)
        self.assertTrue(classification.metadata["selectedReachable"])
        self.assertTrue(classification.metadata["alternativeComplete"])
        self.assertTrue(classification.metadata["portabilityGap"])
        self.assertEqual("portability_gap", ProjectionPolicy().fields(observation, classification)["finding_type"])
        assessed = MigrationAssessor().assess(context(), result.value, analysis)
        project = next(item for item in assessed.value.assessments if item.kind == "project_migration_state")
        self.assertEqual("x86_only", project.state)
        self.assertEqual("satisfied", project.metadata["dimensions"]["target_reachability"])
        self.assertEqual("not_applicable", project.metadata["dimensions"]["test_selection_coverage"])
        self.assertFalse(project.metadata["compiled"])

    def test_inactive_and_unknown_dependencies_are_not_promoted(self) -> None:
        inactive_analysis, inactive_observation = selected_fixture("inactive")
        inactive = MigrationClassifier().classify(context(), DetectionSnapshot((inactive_observation,)), inactive_analysis)
        self.assertEqual("guarded_inactive", inactive.value.classifications[0].impact)
        unknown_analysis, unknown_observation = selected_fixture("unknown")
        unknown = MigrationClassifier().classify(context(), DetectionSnapshot((unknown_observation,)), unknown_analysis)
        self.assertEqual("unknown", unknown.value.classifications[0].impact)
        self.assertFalse(unknown.value.classifications[0].metadata["portabilityGap"])

    def test_selected_dependency_with_incomplete_alternative_stays_blocking_but_not_a_gap(self) -> None:
        analysis, observation = selected_fixture()
        portable = Entity(stable_id("portable"), "implementation", "portable.c")
        alternative = Relation(
            stable_id("alternative"), "alternative_to", analysis.entities[1].id, portable.id,
            (), "medium", "unknown", {"role": "portable", "configuration": "cfg"},
        )
        analysis = AnalysisSnapshot(
            (*analysis.relations, alternative),
            (*analysis.entities, portable),
            analysis.proof_paths,
        )
        observation = Observation(
            observation.id, observation.detector_id, observation.kind, observation.evidence_ids,
            (*observation.relation_ids, alternative.id), observation.confidence,
            observation.status, observation.metadata, observation.knowledge_ids,
        )
        result = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), analysis)
        classification = result.value.classifications[0]
        self.assertEqual("blocking_issue", classification.impact)
        self.assertFalse(classification.metadata["alternativeComplete"])
        self.assertFalse(classification.metadata["portabilityGap"])
        assessed = MigrationAssessor().assess(context(), result.value, analysis)
        project = next(item for item in assessed.value.assessments if item.kind == "project_migration_state")
        self.assertEqual("provisional", project.state)
        self.assertEqual("unknown", project.metadata["dimensions"]["riscv_or_generic_alternative"])
        self.assertFalse(project.metadata["completeness"]["alternativeComplete"])


if __name__ == "__main__":
    unittest.main()
