from __future__ import annotations

import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.pipeline import StagedPipelineRunner, create_knowledge_detection_qualification_profile
from tests.unit.build_selection.support import ROOT, context


class ClassificationAssessmentComponentTests(unittest.TestCase):
    def test_real_static_projects_never_become_ready_from_missing_test_or_build_input(self) -> None:
        roots = (
            Path("/fixtures/avx-avx2-example-code/source"),
            ROOT / "tests/fixtures/generated-entries/folder-matrix/c/before-x86-only",
            ROOT / "tests/fixtures/generated-entries/folder-matrix/cpp/before-x86-only",
        )
        for root in roots:
            with self.subTest(root=str(root)):
                profile = create_knowledge_detection_qualification_profile()
                scan_context = context(root)
                result = StagedPipelineRunner(profile).run(scan_context)
                self.assertTrue(result.success)
                self.assertEqual(result.artifacts, ())
                self.assertIn(result.status, {CompletionStatus.COMPLETE, CompletionStatus.PARTIAL})
                workspace = profile.workspace_collector.collect(scan_context).value
                knowledge = profile.knowledge_provider.load(scan_context).value
                frontend = profile.frontend.analyze(scan_context, workspace).value
                normalized = profile.normalizer.normalize(scan_context, frontend).value
                analysis = profile.analyzer.analyze(scan_context, normalized, knowledge).value
                detections = profile.detector.detect(scan_context, normalized, analysis, knowledge).value
                classifications = profile.classifier.classify(scan_context, detections, analysis).value
                assessments = profile.assessor.assess(scan_context, classifications, analysis).value
                project = next(item for item in assessments.assessments if item.kind == "project_migration_state")
                self.assertNotEqual(project.state, "riscv_ready")
                self.assertFalse(project.metadata["compiled"])
                self.assertFalse(project.metadata["testsExecuted"])
                self.assertEqual(classifications.observations, detections.observations)

    def test_malicious_build_and_test_commands_remain_static_text(self) -> None:
        marker = Path("/tmp/kb-scanner-must-not-run")
        self.assertFalse(marker.exists())
        root = ROOT / "tests/fixtures/classification-assessment/malicious"
        result = StagedPipelineRunner(create_knowledge_detection_qualification_profile()).run(context(root))
        self.assertTrue(result.success)
        self.assertEqual(result.artifacts, ())
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
