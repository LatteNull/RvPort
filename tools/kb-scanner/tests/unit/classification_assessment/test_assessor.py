from __future__ import annotations

import unittest

from kb_scanner.assessors import ASSESSMENT_DIMENSIONS, DIMENSION_STATES, PROJECT_STATES, MigrationAssessor
from kb_scanner.assessors.migration import _project_state
from kb_scanner.classifiers import MigrationClassifier
from kb_scanner.core import (
    AnalysisSnapshot,
    ClassificationSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Entity,
    Relation,
    Observation,
    stable_id,
)
from tests.unit.classification_assessment.support import assessment_scope, context, proof_analysis


def _project(result):
    return next(item for item in result.value.assessments if item.kind == "project_migration_state")


def _alternative(analysis: AnalysisSnapshot, role: str = "generic", status: str = "selected") -> AnalysisSnapshot:
    selector = next((item for item in analysis.entities if item.kind == "architecture_selector"), Entity(stable_id("selector", role), "architecture_selector", "riscv64"))
    target = Entity(stable_id("alt", role), "source_file", f"src/{role}.c")
    relation = Relation(stable_id("alt-rel", role, status), "selects", selector.id, target.id, (), "high", status, {"role": role, "configuration": "cfg"})
    return AnalysisSnapshot((*analysis.relations, relation), (*analysis.entities, selector, target), analysis.proof_paths)


class AssessorTests(unittest.TestCase):
    def test_vocabulary_and_no_input_unknown(self) -> None:
        self.assertEqual(len(ASSESSMENT_DIMENSIONS), 6)
        self.assertIn("unknown", DIMENSION_STATES)
        self.assertIn("riscv_ready", PROJECT_STATES)
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), AnalysisSnapshot())
        self.assertEqual(_project(result).state, "unknown")
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(len(result.value.assessments), 7)

    def test_architecture_independent_and_riscv_ready_require_complete_scope(self) -> None:
        independent = AnalysisSnapshot(entities=(assessment_scope(architectureIndependent=True),))
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), independent)
        self.assertEqual(_project(result).state, "architecture_independent")
        local = Observation(stable_id("architecture-specific"), "LOCAL", "x86_intrinsic", status="confirmed_local")
        classified = MigrationClassifier().classify(context(), DetectionSnapshot((local,)), independent).value
        not_independent = MigrationAssessor().assess(context(), classified, independent)
        self.assertNotEqual(_project(not_independent).state, "architecture_independent")
        ready_analysis = _alternative(AnalysisSnapshot(entities=(assessment_scope(),)))
        ready = MigrationAssessor().assess(context(), ClassificationSnapshot(), ready_analysis)
        project = _project(ready)
        self.assertEqual(project.state, "riscv_ready")
        self.assertTrue(project.metadata["staticScopeOnly"])
        self.assertFalse(project.metadata["compiled"])
        self.assertFalse(project.metadata["testsExecuted"])
        self.assertEqual(ready.status, CompletionStatus.COMPLETE)

    def test_no_x86_hit_with_incomplete_inputs_is_only_provisional(self) -> None:
        source = Entity(stable_id("source"), "source_file", "main.c")
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), AnalysisSnapshot(entities=(source,)))
        self.assertEqual(_project(result).state, "provisional")
        self.assertIn("input_completeness", _project(result).metadata["blockingDimensions"])

    def test_x86_only_and_partial_riscv_come_from_complete_proof(self) -> None:
        base, observation = proof_analysis(status="selected")
        classifications = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), base).value
        x86_analysis = AnalysisSnapshot(base.relations, (*base.entities, assessment_scope()), base.proof_paths)
        x86_only = MigrationAssessor().assess(context(), classifications, x86_analysis)
        self.assertEqual(_project(x86_only).state, "x86_only")
        partial_analysis = _alternative(x86_analysis)
        partial = MigrationAssessor().assess(context(), classifications, partial_analysis)
        self.assertEqual(_project(partial).state, "partial_riscv")
        states = {item.metadata.get("dimension"): item.state for item in partial.value.assessments if item.kind == "migration_dimension"}
        self.assertEqual(states["x86_dependency"], "issue")

    def test_multiarch_without_riscv_and_configuration_conflict(self) -> None:
        base = AnalysisSnapshot(entities=(assessment_scope(),))
        multi = _alternative(_alternative(base, "x86"), "arm")
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), multi)
        self.assertEqual(_project(result).state, "multiarch_without_riscv")
        selected = _alternative(base)
        selected_relation = selected.relations[-1]
        inactive = Relation(
            stable_id("conflict"), selected_relation.kind, selected_relation.source_id, selected_relation.target_id,
            (), "high", "inactive", {"role": "generic", "configuration": "cfg"},
        )
        conflict = AnalysisSnapshot((*selected.relations, inactive), selected.entities)
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), conflict)
        self.assertEqual(_project(result).state, "provisional")
        self.assertTrue(_project(result).metadata["configurationConflict"])

    def test_packaging_and_test_dimensions_are_conservative(self) -> None:
        package = Entity(stable_id("package"), "package_section", "%check")
        test = Entity(stable_id("test"), "test_target", "unit")
        scope = assessment_scope(testNotApplicable=False, testComplete=True, packagingComplete=False)
        analysis = _alternative(AnalysisSnapshot(entities=(scope, package, test)))
        result = MigrationAssessor().assess(context(), ClassificationSnapshot(), analysis)
        dimensions = {item.metadata.get("dimension"): item.state for item in result.value.assessments if item.kind == "migration_dimension"}
        self.assertEqual(dimensions["test_selection_coverage"], "satisfied")
        self.assertEqual(dimensions["packaging_constraint"], "satisfied")

    def test_dangling_classification_references_fail(self) -> None:
        analysis, observation = proof_analysis(status="selected")
        snapshot = MigrationClassifier().classify(context(), DetectionSnapshot((observation,)), analysis).value
        no_observations = ClassificationSnapshot((), snapshot.classifications)
        self.assertEqual(MigrationAssessor().assess(context(), no_observations, analysis).status, CompletionStatus.FAILED)
        self.assertEqual(MigrationAssessor().assess(context(), snapshot, AnalysisSnapshot(entities=analysis.entities)).status, CompletionStatus.FAILED)
        no_proofs = AnalysisSnapshot(analysis.relations, analysis.entities)
        self.assertEqual(MigrationAssessor().assess(context(), snapshot, no_proofs).status, CompletionStatus.FAILED)

    def test_readiness_lattice_monotonically_degrades_when_any_dimension_becomes_unknown(self) -> None:
        satisfied = {name: "satisfied" for name in ASSESSMENT_DIMENSIONS}
        self.assertEqual(
            _project_state(satisfied, {"generic"}, architecture_independent=False, selected_alternative=True, blocker=False, test_issue=False, conflict=False, architecture_dependency_present=False, has_input=True),
            "riscv_ready",
        )
        for dimension in ASSESSMENT_DIMENSIONS:
            degraded = dict(satisfied)
            degraded[dimension] = "unknown"
            with self.subTest(dimension=dimension):
                self.assertNotEqual(
                    _project_state(degraded, {"generic"}, architecture_independent=False, selected_alternative=True, blocker=False, test_issue=False, conflict=False, architecture_dependency_present=False, has_input=True),
                    "riscv_ready",
                )


if __name__ == "__main__":
    unittest.main()
