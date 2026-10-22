from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.adapters.legacy import LegacyPipelineRunner, create_legacy_application
from kb_scanner.core import (
    AnalysisSnapshot,
    AssessmentSnapshot,
    ClassificationSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    Evidence,
    FrontendSnapshot,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    ScanContext,
    SourceLocation,
    SourceSpan,
    StageResult,
)
from kb_scanner.frontends.cpp import ClangCppAdapter, CppFrontend, CppWorkspaceCollector
from kb_scanner.core import stable_id
from kb_scanner.pipeline import PipelineProfile, StagedPipelineRunner


ROOT = Path(__file__).resolve().parents[1]


def make_context(root: Path) -> ScanContext:
    return ScanContext(
        input_root=root,
        output_dir=root / "out",
        rule_dir=ROOT / "rulesets" / "riscv-porting",
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


class _NeverCalledClang:
    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, *args: object) -> StageResult[tuple]:
        self.calls += 1
        raise AssertionError("Clang must not run without a direct compilation context")


class _PartialClang:
    def enrich(self, *args: object) -> StageResult[tuple]:
        diagnostic = Diagnostic(
            code="clang.synthetic-partial",
            stage="frontend.clang",
            severity=DiagnosticSeverity.WARNING,
            message="qualification degradation",
        )
        return StageResult(value=(), status=CompletionStatus.PARTIAL, diagnostics=(diagnostic,))


class _InvalidSubjectTree:
    def analyze_file(self, *args: object) -> StageResult[tuple[Evidence, ...]]:
        unknown_subject = stable_id("unknown-subject")
        span = SourceSpan(SourceLocation("main.c", 1, 1), SourceLocation("main.c", 1, 4))
        evidence = Evidence(
            id=stable_id("bad-evidence", unknown_subject),
            kind="call_expression",
            subject_id=unknown_subject,
            value="bad",
            producer="synthetic",
            parse_mode="test",
            confidence="high",
            location=span,
        )
        return StageResult((evidence,))


class _QualificationDownstream:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.frontend_snapshot: FrontendSnapshot | None = None

    def load(self, context: ScanContext) -> StageResult[KnowledgeSnapshot]:
        self.calls.append("knowledge")
        return StageResult(KnowledgeSnapshot(context.knowledge_id, "1"))

    def normalize(self, context: ScanContext, frontend: FrontendSnapshot) -> StageResult[NormalizedSnapshot]:
        self.calls.append("normalize")
        self.frontend_snapshot = frontend
        return StageResult(NormalizedSnapshot(frontend.entities, frontend.evidence))

    def analyze(
        self,
        context: ScanContext,
        facts: NormalizedSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> StageResult[AnalysisSnapshot]:
        self.calls.append("analyze")
        return StageResult(AnalysisSnapshot())

    def detect(self, *args: object) -> StageResult[DetectionSnapshot]:
        self.calls.append("detect")
        return StageResult(DetectionSnapshot())

    def classify(self, *args: object) -> StageResult[ClassificationSnapshot]:
        self.calls.append("classify")
        return StageResult(ClassificationSnapshot())

    def assess(self, *args: object) -> StageResult[AssessmentSnapshot]:
        self.calls.append("assess")
        return StageResult(AssessmentSnapshot())

    def project(self, *args: object) -> StageResult[tuple]:
        self.calls.append("project")
        return StageResult(())


class FormalFrontendIntegrationTests(unittest.TestCase):
    def test_no_compilation_context_skips_optional_clang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
            context = make_context(root)
            workspace = CppWorkspaceCollector().collect(context).value
            clang = _NeverCalledClang()
            result = CppFrontend(clang=clang).analyze(context, workspace)
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual(clang.calls, 0)
        self.assertTrue(result.value.entities)

    def test_clang_partial_does_not_remove_tree_sitter_baseline(self) -> None:
        from kb_scanner.core import CompilationUnitContext

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("#define LOCAL 1\nint main(void) { return LOCAL; }\n", encoding="utf-8")
            unit = CompilationUnitContext(path=source, tokens=("clang", str(source)), directory=root)
            base = make_context(root)
            context = ScanContext(
                **{
                    name: ((unit,) if name == "compile_contexts" else getattr(base, name))
                    for name in base.__dataclass_fields__
                }
            )
            workspace = CppWorkspaceCollector().collect(context).value
            result = CppFrontend(clang=_PartialClang()).analyze(context, workspace)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertIn("clang.synthetic-partial", {item.code for item in result.diagnostics})
        self.assertIn("macro_definition", {item.kind for item in result.value.evidence})
        self.assertTrue(any(item.producer.startswith("tree-sitter-") for item in result.value.evidence))

    def test_real_tree_sitter_and_clang_results_keep_separate_producers(self) -> None:
        from kb_scanner.core import CompilationUnitContext

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = root / "config.h"
            source = root / "main.c"
            header.write_text("#define VALUE 1\n", encoding="utf-8")
            source.write_text('#include "config.h"\nint main(void) { return VALUE; }\n', encoding="utf-8")
            unit = CompilationUnitContext(
                path=source,
                tokens=("clang", "-I", str(root), str(source)),
                directory=root,
            )
            base = make_context(root)
            context = ScanContext(
                **{
                    name: ((unit,) if name == "compile_contexts" else getattr(base, name))
                    for name in base.__dataclass_fields__
                }
            )
            workspace = CppWorkspaceCollector().collect(context).value
            result = CppFrontend(clang=ClangCppAdapter()).analyze(context, workspace)
        producers = {item.producer for item in result.value.evidence}
        self.assertTrue(any(item.startswith("tree-sitter-") for item in producers))
        self.assertIn("clang@18.1.3", producers)
        include_evidence = [item for item in result.value.evidence if item.kind == "include"]
        self.assertGreaterEqual(len(include_evidence), 2)
        self.assertEqual(len(include_evidence), len({item.id for item in include_evidence}))

    def test_invalid_evidence_subject_stops_frontend_with_structured_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.c").write_text("int main(void);\n", encoding="utf-8")
            context = make_context(root)
            workspace = CppWorkspaceCollector().collect(context).value
            result = CppFrontend(tree_sitter=_InvalidSubjectTree()).analyze(context, workspace)
        self.assertEqual(result.status, CompletionStatus.FAILED)
        self.assertIsNone(result.value)
        self.assertEqual(result.diagnostics[-1].code, "frontend.invalid-subject-reference")

    def test_real_workspace_and_frontend_flow_through_qualification_pipeline_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.cpp").write_text(
                "template <typename T> T same(T value) { return value; }\nint main() { return same(1); }\n",
                encoding="utf-8",
            )
            downstream = _QualificationDownstream()
            profile = PipelineProfile(
                workspace_collector=CppWorkspaceCollector(),
                knowledge_provider=downstream,
                frontend=CppFrontend(),
                normalizer=downstream,
                analyzer=downstream,
                detector=downstream,
                classifier=downstream,
                assessor=downstream,
                report_projector=downstream,
            )
            result = StagedPipelineRunner(profile).run(make_context(root))
            output_exists = (root / "out").exists()
        self.assertTrue(result.success)
        self.assertEqual(result.artifacts, ())
        self.assertFalse(output_exists)
        self.assertEqual(
            downstream.calls,
            ["knowledge", "normalize", "analyze", "detect", "classify", "assess", "project"],
        )
        self.assertTrue(downstream.frontend_snapshot.entities)
        self.assertTrue(downstream.frontend_snapshot.evidence)

    def test_explicit_legacy_oracle_remains_available_to_regression_tests(self) -> None:
        application = create_legacy_application()
        self.assertIsInstance(application._profile.runner, LegacyPipelineRunner)


if __name__ == "__main__":
    unittest.main()
