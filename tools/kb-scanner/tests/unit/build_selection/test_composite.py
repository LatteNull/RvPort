from __future__ import annotations

import unittest

from kb_scanner.core import (
    AnalysisSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    FrontendSnapshot,
    NormalizedFact,
    NormalizedSnapshot,
    StageResult,
    WorkspaceSnapshot,
    stable_id,
)
from kb_scanner.frontends.build import ProjectWorkspaceCollector
from kb_scanner.pipeline.composite import (
    CompositeAnalyzer,
    CompositeDetector,
    CompositeNormalizer,
    CompositeProjectFrontend,
    _merge_frontend,
    _merge_normalized,
)
from tests.unit.build_selection.support import context, flag_knowledge


class CompositeTests(unittest.TestCase):
    def test_composite_frontend_normalizer_analyzer_detector_preserve_both_domains(self) -> None:
        scan_context = context()
        workspace = ProjectWorkspaceCollector().collect(scan_context).value
        frontend_result = CompositeProjectFrontend().analyze(scan_context, workspace)
        self.assertEqual(frontend_result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.kind == "source_file" for item in frontend_result.value.entities))
        self.assertTrue(any(item.kind == "build_file" for item in frontend_result.value.entities))
        normalized_result = CompositeNormalizer().normalize(scan_context, frontend_result.value)
        self.assertEqual(normalized_result.status, CompletionStatus.COMPLETE)
        self.assertTrue(any(item.kind == "symbol" for item in normalized_result.value.facts))
        self.assertTrue(any(item.kind.startswith("build_") for item in normalized_result.value.facts))
        knowledge = flag_knowledge("-mavx", "-mavx2")
        analysis_result = CompositeAnalyzer().analyze(scan_context, normalized_result.value, knowledge)
        self.assertEqual(analysis_result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.kind == "source_file" for item in analysis_result.value.entities))
        self.assertTrue(any(item.kind == "build_argument" for item in analysis_result.value.entities))
        detection_result = CompositeDetector().detect(scan_context, normalized_result.value, analysis_result.value, knowledge)
        self.assertEqual(detection_result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.detector_id == "BUILD.SELECTION" for item in detection_result.value.observations))
        self.assertFalse(any(item.code == "detector.deferred-capabilities" for item in detection_result.diagnostics))

    def test_composite_merges_partial_results_and_propagates_failures(self) -> None:
        diagnostic = Diagnostic("unit.partial", "unit", DiagnosticSeverity.WARNING, "partial")
        entity = Entity(stable_id("entity", "one"), "source_file", "main.c")
        evidence = Evidence(stable_id("evidence", "one"), "symbol", entity.id, "call", "unit", "unit", "high")
        fact = NormalizedFact(stable_id("fact", "one"), "symbol", entity.id, "call", "unit", (evidence.id,))
        frontend = FrontendSnapshot((entity,), (evidence,))
        normalized = NormalizedSnapshot((entity,), (evidence,), (fact,))
        empty_analysis = AnalysisSnapshot()
        empty_detection = DetectionSnapshot()
        complete_frontend = StageResult(frontend)
        partial_frontend = StageResult(FrontendSnapshot(), CompletionStatus.PARTIAL, (diagnostic,))
        merged = _merge_frontend(complete_frontend, partial_frontend)
        self.assertEqual(merged.status, CompletionStatus.PARTIAL)
        self.assertEqual(merged.diagnostics, (diagnostic,))
        failed = StageResult(None, CompletionStatus.FAILED, (diagnostic,))
        self.assertEqual(_merge_frontend(complete_frontend, failed).status, CompletionStatus.FAILED)
        orphan = Evidence(stable_id("evidence", "orphan"), "symbol", stable_id("entity", "missing"), "x", "unit", "unit", "high")
        self.assertEqual(_merge_frontend(StageResult(FrontendSnapshot((entity,), (orphan,)))).status, CompletionStatus.FAILED)

        partial_normalized = StageResult(NormalizedSnapshot(), CompletionStatus.PARTIAL, (diagnostic,))
        self.assertEqual(_merge_normalized(StageResult(normalized), partial_normalized).status, CompletionStatus.PARTIAL)
        self.assertEqual(_merge_normalized(StageResult(normalized), failed).status, CompletionStatus.FAILED)
        orphan_fact = NormalizedFact(stable_id("fact", "orphan"), "symbol", entity.id, "x", "unit", (stable_id("evidence", "missing"),))
        invalid = StageResult(NormalizedSnapshot((entity,), (), (orphan_fact,)))
        self.assertEqual(_merge_normalized(invalid).status, CompletionStatus.FAILED)

        scan_context = context()
        workspace = WorkspaceSnapshot(scan_context.input_root, ("main.c",))
        frontend_stage = CompositeProjectFrontend(_Returning(complete_frontend), _Returning(partial_frontend)).analyze(scan_context, workspace)
        self.assertEqual(frontend_stage.status, CompletionStatus.PARTIAL)
        normalized_stage = CompositeNormalizer(_Returning(StageResult(normalized)), _Returning(partial_normalized)).normalize(scan_context, frontend)
        self.assertEqual(normalized_stage.status, CompletionStatus.PARTIAL)

        knowledge = flag_knowledge()
        self.assertEqual(CompositeAnalyzer(_Returning(failed), _Returning(StageResult(empty_analysis))).analyze(scan_context, normalized, knowledge).status, CompletionStatus.FAILED)
        self.assertEqual(CompositeAnalyzer(_Returning(StageResult(empty_analysis)), _Returning(failed)).analyze(scan_context, normalized, knowledge).status, CompletionStatus.FAILED)
        partial_analysis = StageResult(empty_analysis, CompletionStatus.PARTIAL, (diagnostic,))
        self.assertEqual(CompositeAnalyzer(_Returning(partial_analysis), _Returning(StageResult(empty_analysis))).analyze(scan_context, normalized, knowledge).status, CompletionStatus.PARTIAL)
        self.assertEqual(CompositeAnalyzer(_Returning(StageResult(empty_analysis)), _Returning(StageResult(empty_analysis))).analyze(scan_context, normalized, knowledge).status, CompletionStatus.COMPLETE)

        self.assertEqual(CompositeDetector(_Returning(failed), _Returning(StageResult(empty_detection))).detect(scan_context, normalized, empty_analysis, knowledge).status, CompletionStatus.FAILED)
        self.assertEqual(CompositeDetector(_Returning(StageResult(empty_detection)), _Returning(failed)).detect(scan_context, normalized, empty_analysis, knowledge).status, CompletionStatus.FAILED)
        partial_detection = StageResult(empty_detection, CompletionStatus.PARTIAL, (diagnostic,))
        self.assertEqual(CompositeDetector(_Returning(partial_detection), _Returning(StageResult(empty_detection))).detect(scan_context, normalized, empty_analysis, knowledge).status, CompletionStatus.PARTIAL)
        self.assertEqual(CompositeDetector(_Returning(StageResult(empty_detection)), _Returning(StageResult(empty_detection))).detect(scan_context, normalized, empty_analysis, knowledge).status, CompletionStatus.COMPLETE)


class _Returning:
    def __init__(self, result: StageResult[object]) -> None:
        self.result = result

    def analyze(self, *_: object) -> StageResult[object]:
        return self.result

    def normalize(self, *_: object) -> StageResult[object]:
        return self.result

    def detect(self, *_: object) -> StageResult[object]:
        return self.result


if __name__ == "__main__":
    unittest.main()
