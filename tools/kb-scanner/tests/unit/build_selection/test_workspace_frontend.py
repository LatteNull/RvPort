from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from kb_scanner.core import CompletionStatus, StageResult, WorkspaceSnapshot
from kb_scanner.frontends.build import BuildFrontend, ProjectWorkspaceCollector
from tests.unit.build_selection.support import FIXTURE, context


class _Collector:
    def __init__(self, result: StageResult[WorkspaceSnapshot]) -> None:
        self.result = result

    def collect(self, *_: object) -> StageResult[WorkspaceSnapshot]:
        return self.result


class WorkspaceFrontendTests(unittest.TestCase):
    def test_project_workspace_combines_cpp_and_build_inputs(self) -> None:
        result = ProjectWorkspaceCollector().collect(context())
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        files = set(result.value.files)
        self.assertTrue({"main.c", "Makefile", "configure", "configure.ac", "package.spec", "compile_commands.json"} <= files)
        self.assertIn(".cmake/api/v1/reply/codemodel-v2.json", files)
        self.assertIn("meson-info/intro-targets.json", files)
        self.assertIn("ctest-v1.json", files)

    def test_single_file_missing_excludes_and_escape_are_handled(self) -> None:
        make = context(FIXTURE / "Makefile")
        result = ProjectWorkspaceCollector().collect(make)
        self.assertEqual(result.value.files, ("Makefile",))
        missing = context(FIXTURE / "missing")
        self.assertEqual(ProjectWorkspaceCollector().collect(missing).status, CompletionStatus.FAILED)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "build").mkdir()
            (root / "build" / "Makefile").write_text("A=1", encoding="utf-8")
            (root / "skip.mk").write_text("A=1", encoding="utf-8")
            (root / "main.c").write_text("int x;", encoding="utf-8")
            result = ProjectWorkspaceCollector().collect(context(root, excludes=("build",)))
            self.assertNotIn("build/Makefile", result.value.files)
            self.assertIn("skip.mk", result.value.files)
            excluded = replace(context(root), exclude_paths=("skip.mk",))
            self.assertNotIn("skip.mk", ProjectWorkspaceCollector().collect(excluded).value.files)
        source_result = ProjectWorkspaceCollector().collect(context(FIXTURE / "main.c"))
        self.assertEqual(source_result.value.files, ("main.c",))

    def test_workspace_discovery_and_build_path_failures_are_bounded(self) -> None:
        scan_context = context()
        cpp_snapshot = StageResult(WorkspaceSnapshot(scan_context.input_root, ()))
        collector = ProjectWorkspaceCollector(_Collector(cpp_snapshot))
        with patch.object(Path, "rglob", side_effect=OSError("discovery")):
            self.assertEqual(collector.collect(scan_context).status, CompletionStatus.FAILED)
        failed = StageResult(None, CompletionStatus.FAILED)
        self.assertEqual(ProjectWorkspaceCollector(_Collector(failed)).collect(scan_context).status, CompletionStatus.FAILED)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "bad.mk").write_text("A=1", encoding="utf-8")
            local_context = context(root)
            local_cpp = StageResult(WorkspaceSnapshot(root, ()))
            original_resolve = Path.resolve

            def selective_resolve(path: Path, *args: object, **kwargs: object) -> Path:
                if path.name == "bad.mk":
                    raise OSError("unreadable")
                return original_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", selective_resolve):
                result = ProjectWorkspaceCollector(_Collector(local_cpp)).collect(local_context)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertTrue(any(item.code == "workspace.build-path-unreadable" for item in result.diagnostics))

            outside = root.parent / "outside.mk"
            outside.write_text("A=1", encoding="utf-8")
            (root / "linked.mk").symlink_to(outside)
            result = ProjectWorkspaceCollector(_Collector(local_cpp)).collect(local_context)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertTrue(any(item.code == "workspace.build-path-escape" for item in result.diagnostics))

    def test_build_frontend_routes_all_inputs_and_retains_partial_diagnostics(self) -> None:
        workspace = ProjectWorkspaceCollector().collect(context()).value
        result = BuildFrontend().analyze(context(), workspace)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        kinds = {item.kind for item in result.value.evidence}
        self.assertTrue({"build_assignment", "build_arch_probe", "build_branch", "build_source", "build_argument", "build_target", "build_dependency", "build_arch_constraint", "build_unsupported"} <= kinds)
        producers = {item.producer for item in result.value.evidence}
        self.assertTrue({"tree-sitter-make+bounded-evaluator", "tree-sitter-bash+bounded-autoconf", "bounded-m4-recognizer", "cmake-file-api-reader", "meson-introspection-reader", "ctest-metadata-reader", "compilation-database-build-reader", "bounded-rpm-parser"} <= producers)
        entity_ids = {item.id for item in result.value.entities}
        self.assertTrue(all(item.subject_id in entity_ids for item in result.value.evidence))

    def test_frontend_reader_failures_size_budget_and_empty_workspace_degrade_safely(self) -> None:
        workspace = WorkspaceSnapshot(FIXTURE, ("Makefile",))
        result = BuildFrontend(reader=lambda _: (_ for _ in ()).throw(OSError("no"))).analyze(context(), workspace)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.value.evidence, ())
        limited = BuildFrontend(max_bytes=1).analyze(context(), workspace)
        self.assertEqual(limited.status, CompletionStatus.PARTIAL)
        self.assertEqual(BuildFrontend().analyze(context(), WorkspaceSnapshot(FIXTURE, ())).status, CompletionStatus.COMPLETE)
        with self.assertRaises(ValueError):
            BuildFrontend(max_bytes=0)


if __name__ == "__main__":
    unittest.main()
