from __future__ import annotations

import unittest

from kb_scanner.assessors import MigrationAssessor
from kb_scanner.classifiers import MigrationClassifier
from kb_scanner.core import CompletionStatus
from kb_scanner.frontends.build import ProjectWorkspaceCollector
from kb_scanner.pipeline import StagedPipelineRunner, create_knowledge_detection_qualification_profile
from tests.unit.classification_assessment.support import ROOT
from tests.unit.build_selection.support import context


class PipelineContractTests(unittest.TestCase):
    def test_qualification_reaches_real_classification_and_assessment_without_artifacts(self) -> None:
        scan_context = context()
        profile = create_knowledge_detection_qualification_profile()
        self.assertIsInstance(profile.classifier, MigrationClassifier)
        self.assertIsInstance(profile.assessor, MigrationAssessor)
        result = StagedPipelineRunner(profile).run(scan_context)
        self.assertTrue(result.success)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.artifacts, ())
        self.assertFalse((scan_context.output_dir / "scan-result.json").exists())

        workspace = profile.workspace_collector.collect(scan_context).value
        knowledge = profile.knowledge_provider.load(scan_context).value
        frontend = profile.frontend.analyze(scan_context, workspace).value
        normalized = profile.normalizer.normalize(scan_context, frontend).value
        analysis = profile.analyzer.analyze(scan_context, normalized, knowledge).value
        detections = profile.detector.detect(scan_context, normalized, analysis, knowledge).value
        classifications = profile.classifier.classify(scan_context, detections, analysis).value
        assessments = profile.assessor.assess(scan_context, classifications, analysis).value
        self.assertTrue(classifications.classifications)
        self.assertEqual(classifications.observations, detections.observations)
        project = next(item for item in assessments.assessments if item.kind == "project_migration_state")
        self.assertIn(project.state, {"partial_riscv", "provisional", "x86_only"})
        self.assertFalse(project.metadata["compiled"])
        self.assertFalse(project.metadata["testsExecuted"])

    def test_malicious_project_is_only_collected_as_static_input(self) -> None:
        root = ROOT / "tests/fixtures/classification-assessment/malicious"
        marker = __import__("pathlib").Path("/tmp/kb-scanner-must-not-run")
        self.assertFalse(marker.exists())
        scan_context = context(root)
        workspace = ProjectWorkspaceCollector().collect(scan_context)
        self.assertEqual(workspace.status, CompletionStatus.COMPLETE)
        self.assertIn("Makefile", workspace.value.files)
        self.assertIn("package.spec", workspace.value.files)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
