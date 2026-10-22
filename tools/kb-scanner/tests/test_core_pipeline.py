from __future__ import annotations

import math
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from kb_scanner.core import (
    AnalysisSnapshot,
    Assessment,
    AssessmentSnapshot,
    ClassificationSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    FrontendSnapshot,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    Observation,
    PipelineResult,
    Relation,
    ScanContext,
    SourceLocation,
    SourceSpan,
    StageResult,
    WorkspaceSnapshot,
    merge_diagnostics,
    normalize_project_path,
    stable_id,
)
from kb_scanner.core.metadata import to_json_compatible
from kb_scanner.pipeline import PipelineProfile, StagedPipelineRunner


ROOT = Path(__file__).resolve().parents[1]


def make_context(root: Path) -> ScanContext:
    return ScanContext(
        input_root=root,
        output_dir=root / "out",
        rule_dir=root / "rules",
        languages=("c", "cpp"),
        excludes=(".git", "build"),
        exclude_paths=(),
        formats=("json", "html"),
        context_infer="auto",
        target_arch="riscv64",
        include_inactive_branches=False,
        include_comment_hints=True,
        locale="zh-CN",
        compile_commands_path=None,
        compile_contexts=(),
        scan_mode="source_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="riscv-porting@1",
        scanner_name="kb-scanner",
        scanner_version="0.1.0",
    )


class _RecordingStages:
    def __init__(self, *, stop_at: str | None = None, diagnostic: Diagnostic | None = None) -> None:
        self.calls: list[str] = []
        self.contexts: list[ScanContext] = []
        self.stop_at = stop_at
        self.diagnostic = diagnostic

    def _record(self, name: str, context: ScanContext, value: object) -> StageResult:
        self.calls.append(name)
        self.contexts.append(context)
        diagnostics = (self.diagnostic,) if self.diagnostic and name in {"frontend", "detector"} else ()
        if self.stop_at == name:
            return StageResult(value=None, status=CompletionStatus.UNAVAILABLE, diagnostics=diagnostics)
        return StageResult(value=value, status=CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE, diagnostics=diagnostics)

    def collect(self, context: ScanContext) -> StageResult[WorkspaceSnapshot]:
        return self._record("workspace", context, WorkspaceSnapshot(context.input_root, ("main.c",)))

    def load(self, context: ScanContext) -> StageResult[KnowledgeSnapshot]:
        return self._record("knowledge", context, KnowledgeSnapshot("rules", "1"))

    def analyze(self, context: ScanContext, value: object, knowledge: KnowledgeSnapshot | None = None) -> StageResult:
        if isinstance(value, WorkspaceSnapshot):
            return self._record("frontend", context, FrontendSnapshot())
        if knowledge is None:
            raise AssertionError("Analyzer must receive the KnowledgeSnapshot")
        return self._record("analyzer", context, AnalysisSnapshot())

    def normalize(self, context: ScanContext, value: FrontendSnapshot) -> StageResult[NormalizedSnapshot]:
        return self._record("normalizer", context, NormalizedSnapshot(value.entities, value.evidence))

    def detect(self, context: ScanContext, *values: object) -> StageResult[DetectionSnapshot]:
        return self._record("detector", context, DetectionSnapshot())

    def classify(self, context: ScanContext, *values: object) -> StageResult[ClassificationSnapshot]:
        return self._record("classifier", context, ClassificationSnapshot())

    def assess(self, context: ScanContext, *values: object) -> StageResult[AssessmentSnapshot]:
        return self._record("assessor", context, AssessmentSnapshot())

    def project(self, context: ScanContext, *values: object) -> StageResult[tuple]:
        return self._record("projector", context, ())


def make_profile(stages: _RecordingStages) -> PipelineProfile:
    return PipelineProfile(
        workspace_collector=stages,
        knowledge_provider=stages,
        frontend=stages,
        normalizer=stages,
        analyzer=stages,
        detector=stages,
        classifier=stages,
        assessor=stages,
        report_projector=stages,
    )


class CoreDomainContractTests(unittest.TestCase):
    def test_project_relative_identity_is_stable_across_absolute_roots(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_path = Path(first) / "src" / "main.c"
            second_path = Path(second) / "src" / "main.c"
            relative_first = normalize_project_path(first_path, Path(first))
            relative_second = normalize_project_path(second_path, Path(second))
        self.assertEqual(relative_first, "src/main.c")
        self.assertEqual(relative_first, relative_second)
        self.assertEqual(
            stable_id("entity", relative_first, 7, "clang"),
            stable_id("entity", relative_second, 7, "clang"),
        )
        self.assertRegex(stable_id("entity", "src/main.c"), r"^[0-9a-f]{64}$")
        with self.assertRaises(ValueError):
            stable_id("entity", Path("/machine/specific/main.c"))

    def test_domain_objects_are_frozen_slotted_and_preserve_provenance(self) -> None:
        span = SourceSpan(SourceLocation("src/main.c", 3, 2), SourceLocation("src/main.c", 3, 8))
        entity_id = stable_id("entity", "src/main.c", "function", "add")
        clang_evidence_id = stable_id("evidence", entity_id, "clang", span)
        tree_evidence_id = stable_id("evidence", entity_id, "tree-sitter", span)
        entity = Entity(entity_id, "function", "add", span, {"nested": ["x86"]})
        clang_evidence = Evidence(
            clang_evidence_id,
            "call",
            entity.id,
            "_mm_add_ps",
            "clang",
            "compile-context",
            "high",
            span,
            ("clang-facts@1",),
        )
        tree_evidence = Evidence(
            tree_evidence_id,
            "call",
            entity.id,
            "_mm_add_ps",
            "tree-sitter",
            "syntax",
            "medium",
            span,
        )
        relation = Relation(
            stable_id("relation", "calls", entity.id, entity.id),
            "calls",
            entity.id,
            entity.id,
            (clang_evidence.id, tree_evidence.id),
        )
        observation = Observation(
            stable_id("observation", "x86-call", relation.id),
            "x86-call-detector",
            "x86-call",
            (clang_evidence.id, tree_evidence.id),
            (relation.id,),
        )
        assessment = Assessment(
            stable_id("assessment", "migration", observation.id),
            "migration",
            "unknown",
            observation.evidence_ids,
            observation.relation_ids,
        )

        self.assertNotEqual(clang_evidence.id, tree_evidence.id)
        self.assertEqual(set(relation.evidence_ids), {clang_evidence.id, tree_evidence.id})
        self.assertEqual(clang_evidence.knowledge_sources, ("clang-facts@1",))
        self.assertFalse(hasattr(entity, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            entity.name = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            entity.properties["new"] = True  # type: ignore[index]
        self.assertEqual(assessment.state, "unknown")

    def test_metadata_is_immutable_json_safe_and_convertible(self) -> None:
        entity = Entity(stable_id("entity", "p"), "file", "p", properties={"items": [1, {"ok": True}]})
        self.assertEqual(to_json_compatible(entity.properties), {"items": [1, {"ok": True}]})
        for invalid in ({"path": Path("src/main.c")}, {"set": {1}}, {"nan": math.nan}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(TypeError):
                    Entity(stable_id("entity", repr(invalid)), "file", "p", properties=invalid)

    def test_ids_and_spans_reject_invalid_references_and_locations(self) -> None:
        with self.assertRaises(ValueError):
            SourceLocation("/absolute/main.c", 1)
        with self.assertRaises(ValueError):
            SourceSpan(SourceLocation("a.c", 2), SourceLocation("a.c", 1))
        with self.assertRaises(ValueError):
            Evidence("bad", "call", stable_id("entity", "a"), "x", "p", "syntax", "high")
        with self.assertRaises(ValueError):
            Relation(stable_id("relation", "a"), "calls", "bad", stable_id("entity", "b"))

    def test_diagnostics_deduplicate_in_stable_first_seen_order(self) -> None:
        first = Diagnostic("one", "frontend", DiagnosticSeverity.WARNING, "one")
        duplicate = Diagnostic("one", "frontend", DiagnosticSeverity.WARNING, "one")
        second = Diagnostic("two", "detector", DiagnosticSeverity.INFO, "two")
        self.assertEqual(merge_diagnostics((first, second), (duplicate,)), (first, second))

    def test_core_and_pipeline_import_boundaries_exclude_implementation_types(self) -> None:
        forbidden = ("tree_sitter", "clang", "networkx", "pydantic", "kb_scanner.models", "ProjectFacts", "Finding")
        sources = [
            path.read_text(encoding="utf-8")
            for package in (ROOT / "kb_scanner" / "core", ROOT / "kb_scanner" / "pipeline")
            for path in package.glob("*.py")
        ]
        combined = "\n".join(sources)
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


class StagedPipelineContractTests(unittest.TestCase):
    def test_complete_pipeline_uses_fixed_order_and_same_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            stages = _RecordingStages()
            result = StagedPipelineRunner(make_profile(stages)).run(context)
        self.assertEqual(
            stages.calls,
            ["workspace", "knowledge", "frontend", "normalizer", "analyzer", "detector", "classifier", "assessor", "projector"],
        )
        self.assertTrue(all(item is context for item in stages.contexts))
        self.assertEqual(result, PipelineResult(True, 0, CompletionStatus.COMPLETE))

    def test_partial_diagnostic_continues_and_is_deduplicated(self) -> None:
        diagnostic = Diagnostic("fallback", "frontend", DiagnosticSeverity.WARNING, "using baseline")
        with tempfile.TemporaryDirectory() as tmp:
            stages = _RecordingStages(diagnostic=diagnostic)
            result = StagedPipelineRunner(make_profile(stages)).run(make_context(Path(tmp)))
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.diagnostics, (diagnostic,))
        self.assertEqual(stages.calls[-1], "projector")

    def test_unavailable_required_value_stops_dependent_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stages = _RecordingStages(stop_at="frontend")
            result = StagedPipelineRunner(make_profile(stages)).run(make_context(Path(tmp)))
        self.assertEqual(result.status, CompletionStatus.UNAVAILABLE)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(stages.calls, ["workspace", "knowledge", "frontend"])
        self.assertEqual(result.artifacts, ())

    def test_affecting_diagnostic_changes_exit_code_after_projection(self) -> None:
        diagnostic = Diagnostic(
            "invalid-rules",
            "knowledge",
            DiagnosticSeverity.ERROR,
            "invalid rules",
            affects_exit_code=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            stages = _RecordingStages(diagnostic=diagnostic)
            result = StagedPipelineRunner(make_profile(stages)).run(make_context(Path(tmp)))
        self.assertEqual(result.exit_code, 1)
        self.assertFalse(result.success)
        self.assertEqual(stages.calls[-1], "projector")

    def test_stage_exception_becomes_fatal_without_fake_artifacts(self) -> None:
        class ExplodingStages(_RecordingStages):
            def normalize(self, context: ScanContext, value: FrontendSnapshot) -> StageResult[NormalizedSnapshot]:
                raise RuntimeError("broken invariant")

        with tempfile.TemporaryDirectory() as tmp:
            stages = ExplodingStages()
            result = StagedPipelineRunner(make_profile(stages)).run(make_context(Path(tmp)))
        self.assertEqual(result.status, CompletionStatus.FAILED)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.artifacts, ())
        self.assertEqual(result.diagnostics[-1].code, "pipeline.internal-error")

    def test_projector_failure_does_not_publish_partial_artifacts(self) -> None:
        class FailedProjectorStages(_RecordingStages):
            def project(self, context: ScanContext, *values: object) -> StageResult[tuple]:
                self.calls.append("projector")
                self.contexts.append(context)
                diagnostic = Diagnostic(
                    "projection-failed",
                    "projector",
                    DiagnosticSeverity.ERROR,
                    "projection failed",
                    affects_exit_code=True,
                )
                return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(diagnostic,))

        with tempfile.TemporaryDirectory() as tmp:
            stages = FailedProjectorStages()
            result = StagedPipelineRunner(make_profile(stages)).run(make_context(Path(tmp)))
        self.assertEqual(result.status, CompletionStatus.FAILED)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.artifacts, ())
        self.assertEqual(stages.calls[-1], "projector")

    def test_profile_rejects_missing_component(self) -> None:
        stages = _RecordingStages()
        with self.assertRaises(ValueError):
            PipelineProfile(stages, stages, stages, None, stages, stages, stages, stages, stages)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
