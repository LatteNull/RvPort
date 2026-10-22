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

    def test_real_avx_makefiles_match_all_24_manual_flag_oracles(self) -> None:
        source = Path("/fixtures/avx-avx2-example-code/source")
        self.assertTrue(source.is_dir(), "compose.test.yml must mount the real AVX fixture read-only")
        baseline = json.loads((ROOT / "tests/fixtures/build-selection/avx-make-baseline.json").read_text(encoding="utf-8"))
        expected = sorted(
            (
                item["path"], item["line"], item["startColumn"], item["endColumn"],
                item["flag"], item["variable"], item["target"], item["expectedStatus"],
            )
            for item in baseline["entries"]
        )
        scan_context = context(source)
        workspace = ProjectWorkspaceCollector().collect(scan_context)
        self.assertEqual(workspace.status, CompletionStatus.COMPLETE)
        frontend = BuildFrontend().analyze(scan_context, workspace.value)
        actual_evidence = [
            item for item in frontend.value.evidence
            if item.kind == "build_argument" and item.value in {"-mavx", "-mavx2", "-mfma", "-msse", "-msse2", "-msse3"}
        ]
        actual = sorted(
            (
                item.location.start.path, item.location.start.line, item.location.start.column,
                item.location.end.column, item.value, item.metadata["variable"],
                item.metadata["target"], item.metadata["selectionStatus"],
            )
            for item in actual_evidence
        )
        self.assertEqual(actual, expected)

        normalized = BuildEvidenceNormalizer().normalize(scan_context, frontend.value)
        analysis = BuildSelectionAnalyzer().analyze(scan_context, normalized.value, flag_knowledge("-mavx", "-mavx2", "-mfma", "-msse", "-msse2", "-msse3"))
        selected = [
            item for item in analysis.value.relations
            if item.kind == "adds_argument" and item.status == "selected" and item.metadata.get("value") in {"-mavx", "-mavx2", "-mfma", "-msse", "-msse2", "-msse3"}
        ]
        self.assertEqual(len(selected), 24)
        observations = BuildSelectionDetector().detect(scan_context, normalized.value, analysis.value, flag_knowledge("-mavx", "-mavx2", "-mfma", "-msse", "-msse2", "-msse3"))
        self.assertEqual(sum(item.kind == "build_selected_x86_dependency" for item in observations.value.observations), 24)


if __name__ == "__main__":
    unittest.main()
