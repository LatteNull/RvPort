from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.assessors import MigrationAssessor
from kb_scanner.classifiers import MigrationClassifier
from kb_scanner.core import ClassificationSnapshot, DetectionSnapshot, KnowledgeSnapshot, NormalizedSnapshot, stable_id
from kb_scanner.frontends.build import ProjectWorkspaceCollector
from kb_scanner.knowledge import GeneratedFactsKnowledgeProvider
from kb_scanner.pipeline.composite import CompositeAnalyzer, CompositeDetector, CompositeNormalizer, CompositeProjectFrontend
from kb_scanner.pipeline.qualification import create_knowledge_detection_qualification_profile
from tests.unit.knowledge_detection.support import make_context


class QualificationProfileTests(unittest.TestCase):
    def test_factory_wires_real_pipeline_and_noop_projector(self) -> None:
        profile = create_knowledge_detection_qualification_profile()
        self.assertIsInstance(profile.workspace_collector, ProjectWorkspaceCollector)
        self.assertIsInstance(profile.knowledge_provider, GeneratedFactsKnowledgeProvider)
        self.assertIsInstance(profile.frontend, CompositeProjectFrontend)
        self.assertIsInstance(profile.normalizer, CompositeNormalizer)
        self.assertIsInstance(profile.analyzer, CompositeAnalyzer)
        self.assertIsInstance(profile.detector, CompositeDetector)
        self.assertIsInstance(profile.classifier, MigrationClassifier)
        self.assertIsInstance(profile.assessor, MigrationAssessor)
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            analysis = profile.analyzer.analyze(
                context,
                NormalizedSnapshot(),
                KnowledgeSnapshot(stable_id("knowledge"), "1"),
            ).value
            classification = profile.classifier.classify(context, DetectionSnapshot(), analysis).value
            assessment = profile.assessor.assess(context, classification, analysis).value
            projection = profile.report_projector.project(context)
        self.assertEqual(analysis.relations, ())
        self.assertEqual(classification, ClassificationSnapshot())
        self.assertEqual(len(assessment.assessments), 7)
        project = next(item for item in assessment.assessments if item.kind == "project_migration_state")
        self.assertEqual(project.state, "provisional")
        self.assertTrue(project.metadata["staticScopeOnly"])
        self.assertFalse(project.metadata["compiled"])
        self.assertFalse(project.metadata["testsExecuted"])
        self.assertEqual(projection.value, ())


if __name__ == "__main__":
    unittest.main()
