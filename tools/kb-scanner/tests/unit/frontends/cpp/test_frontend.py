from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import (
    CompilationUnitContext,
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    Evidence,
    StageResult,
    WorkspaceSnapshot,
    stable_id,
)
from kb_scanner.frontends.cpp.frontend import CppFrontend, _unit_relative_path
from kb_scanner.frontends.cpp.vocabulary import make_evidence, make_source_file_entity
from tests.unit.frontends.cpp.support import make_context, span


def diagnostic(code: str) -> Diagnostic:
    return Diagnostic(code, "fake", DiagnosticSeverity.WARNING, code, producer="fake")


class FakeTree:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def analyze_file(self, context, root, relative_path, entity):
        self.calls.append((context, root, relative_path, entity))
        return self.results.pop(0)


class FakeClang:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def enrich(self, context, workspace, unit, entities):
        self.calls.append((context, workspace, unit, entities))
        return self.results.pop(0)


class CompositeFrontendTests(unittest.TestCase):
    def test_empty_workspace_and_no_context_are_complete_without_adapter_calls(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tree, clang = FakeTree([]), FakeClang([])
            workspace = WorkspaceSnapshot(root, ())
            context = make_context(root)
            result = CppFrontend(tree, clang).analyze(context, workspace)
            self.assertEqual(result.status, CompletionStatus.COMPLETE)
            self.assertEqual(result.value.entities, ())
            self.assertEqual(tree.calls, [])
            self.assertEqual(clang.calls, [])

    def test_context_matching_outside_and_multiple_entries_preserve_call_order_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root, outside = Path(raw), Path(outside_raw)
            source = root / "a.c"
            source.write_text("", encoding="utf-8")
            units = (CompilationUnitContext(source, entry_index=0), CompilationUnitContext(source, entry_index=1), CompilationUnitContext(outside / "x.c", entry_index=2))
            entity = make_source_file_entity("a.c", ("c",), "0.1.0")
            base = make_evidence(kind="include", subject_id=entity.id, value="x.h", producer="tree", parse_mode="base", confidence="high", span=span("a.c"))
            clang_results = [
                StageResult((make_evidence(kind="include", subject_id=entity.id, value="x.h", producer="clang", parse_mode="clang", confidence="high", span=span("a.c"), context_id=str(i)),))
                for i in range(2)
            ]
            tree, clang = FakeTree([StageResult((base,))]), FakeClang(clang_results)
            context = make_context(root, compile_contexts=units)
            workspace = WorkspaceSnapshot(root, ("a.c",))
            result = CppFrontend(tree, clang).analyze(context, workspace)
            self.assertEqual(len(clang.calls), 2)
            self.assertEqual([call[2].entry_index for call in clang.calls], [0, 1])
            self.assertIs(tree.calls[0][0], context)
            self.assertTrue(all(call[0] is context and call[1] is workspace for call in clang.calls))
            self.assertEqual(len(result.value.evidence), 3)

    def test_tree_status_propagation_and_failure_stops_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = WorkspaceSnapshot(root, ("a.c", "b.c"))
            partial = FakeTree([StageResult((), CompletionStatus.PARTIAL, (diagnostic("partial"),)), StageResult(())])
            result = CppFrontend(partial).analyze(make_context(root), workspace)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            failed = FakeTree([StageResult(None, CompletionStatus.FAILED, (diagnostic("failed"),))])
            result = CppFrontend(failed).analyze(make_context(root), workspace)
            self.assertEqual(result.status, CompletionStatus.FAILED)
            self.assertIsNone(result.value)
            self.assertEqual(len(failed.calls), 1)

    def test_clang_all_degraded_statuses_keep_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "a.c"
            source.touch()
            unit = CompilationUnitContext(source)
            workspace = WorkspaceSnapshot(root, ("a.c",))
            entity = make_source_file_entity("a.c", ("c",), "0.1.0")
            base = make_evidence(kind="comment", subject_id=entity.id, value="base", producer="tree", parse_mode="base", confidence="h", span=span("a.c"))
            for status, value in ((CompletionStatus.PARTIAL, ()), (CompletionStatus.UNAVAILABLE, None), (CompletionStatus.FAILED, None)):
                with self.subTest(status=status):
                    clang = FakeClang([StageResult(value, status, (diagnostic(status.value),))])
                    result = CppFrontend(FakeTree([StageResult((base,))]), clang).analyze(make_context(root, compile_contexts=(unit,)), workspace)
                    self.assertEqual(result.status, CompletionStatus.PARTIAL)
                    self.assertEqual(result.value.evidence, (base,))

    def test_diagnostics_keep_first_seen_order_and_duplicates_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = WorkspaceSnapshot(root, ("a.c", "b.c"))
            shared, second = diagnostic("shared"), diagnostic("second")
            tree = FakeTree([StageResult((), diagnostics=(shared,)), StageResult((), diagnostics=(shared, second))])
            result = CppFrontend(tree).analyze(make_context(root), workspace)
            self.assertEqual([item.code for item in result.diagnostics], ["shared", "second"])

    def test_unknown_subject_fails_while_cross_producer_facts_and_sorting_survive(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = WorkspaceSnapshot(root, ("z.c", "a.c"))
            good_entity = make_source_file_entity("z.c", ("c",), "0.1.0")
            first = make_evidence(kind="include", subject_id=good_entity.id, value="x", producer="one", parse_mode="m", confidence="h", span=span("z.c"))
            second = make_evidence(kind="include", subject_id=good_entity.id, value="x", producer="two", parse_mode="m", confidence="h", span=span("z.c"))
            result = CppFrontend(FakeTree([StageResult((first, second, first)), StageResult(())])).analyze(make_context(root), workspace)
            self.assertEqual([item.name for item in result.value.entities], ["a.c", "z.c"])
            self.assertEqual(len(result.value.evidence), 2)
            invalid = Evidence(stable_id("invalid"), "include", stable_id("missing"), "x", "p", "m", "h", span("z.c"))
            failed = CppFrontend(FakeTree([StageResult((invalid,)), StageResult(())])).analyze(make_context(root), workspace)
            self.assertEqual(failed.status, CompletionStatus.FAILED)
            self.assertEqual(failed.diagnostics[-1].code, "frontend.invalid-subject-reference")

    def test_unit_relative_path_accepts_project_file_and_rejects_outside(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw)
            self.assertEqual(_unit_relative_path(root / "a.c", root), "a.c")
            self.assertIsNone(_unit_relative_path(Path(outside_raw) / "a.c", root))


if __name__ == "__main__":
    unittest.main()
