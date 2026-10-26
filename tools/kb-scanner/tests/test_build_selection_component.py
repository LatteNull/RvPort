from __future__ import annotations

import json
import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.frontends.build import BuildFrontend, ProjectWorkspaceCollector
from kb_scanner.normalization import BuildEvidenceNormalizer
from kb_scanner.analyzers import BuildSelectionAnalyzer
from kb_scanner.detectors import BuildSelectionDetector
from kb_scanner.pipeline import StagedPipelineRunner, create_knowledge_detection_qualification_profile
from tests.unit.build_selection.support import ROOT, context, flag_knowledge


class BuildSelectionComponentTests(unittest.TestCase):
    def test_real_static_project_reaches_build_observations_without_artifacts(self) -> None:
        scan_context = context()
        profile = create_knowledge_detection_qualification_profile()
        result = StagedPipelineRunner(profile).run(scan_context)
        self.assertTrue(result.success)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.artifacts, ())
        workspace = profile.workspace_collector.collect(scan_context).value
        self.assertIsInstance(profile.workspace_collector, ProjectWorkspaceCollector)
        frontend = profile.frontend.analyze(scan_context, workspace).value
        knowledge = profile.knowledge_provider.load(scan_context).value
        normalized = profile.normalizer.normalize(scan_context, frontend).value
        analysis = profile.analyzer.analyze(scan_context, normalized, knowledge).value
        detections = profile.detector.detect(scan_context, normalized, analysis, knowledge).value
        self.assertTrue(any(item.kind == "adds_argument" for item in analysis.relations))
        self.assertTrue(any(item.detector_id == "BUILD.SELECTION" for item in detections.observations))
        self.assertFalse((scan_context.output_dir / "scan-result.json").exists())

if __name__ == "__main__":
    unittest.main()
