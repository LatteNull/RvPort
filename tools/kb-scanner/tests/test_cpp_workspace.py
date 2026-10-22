from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus, ScanContext
from kb_scanner.frontends.cpp import CppWorkspaceCollector


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "formal-cpp-frontend" / "src"


def make_context(input_path: Path, **overrides: object) -> ScanContext:
    values = {
        "input_root": input_path,
        "output_dir": input_path.parent / "out",
        "rule_dir": ROOT / "rulesets" / "riscv-porting",
        "languages": ("c", "cpp"),
        "excludes": (".git", "build"),
        "exclude_paths": (),
        "formats": ("json", "html"),
        "context_infer": "auto",
        "target_arch": "riscv64",
        "include_inactive_branches": False,
        "include_comment_hints": True,
        "locale": "zh-CN",
        "compile_commands_path": None,
        "compile_contexts": (),
        "scan_mode": "source_context",
        "rule_pack_id": "riscv-porting",
        "rule_pack_version": "1",
        "knowledge_id": "riscv-porting@1",
        "scanner_name": "kb-scanner",
        "scanner_version": "0.1.0",
    }
    values.update(overrides)
    return ScanContext(**values)


class CppWorkspaceCollectorTests(unittest.TestCase):
    def test_directory_collection_is_deterministic_and_keeps_test_sources(self) -> None:
        context = make_context(FIXTURE, excludes=("generated",))
        first = CppWorkspaceCollector().collect(context)
        second = CppWorkspaceCollector().collect(context)
        self.assertEqual(first.status, CompletionStatus.COMPLETE)
        self.assertEqual(first, second)
        self.assertEqual(first.value.root, FIXTURE.resolve())
        self.assertEqual(
            first.value.files,
            (
                "ambiguous.h",
                "comments.c",
                "complete.c",
                "complete.cpp",
                "incomplete.cpp",
                "tests/x86_test.cpp",
            ),
        )

    def test_language_and_exclude_path_filters_are_applied(self) -> None:
        result = CppWorkspaceCollector().collect(
            make_context(FIXTURE, languages=("c",), exclude_paths=("comments.c", "generated"))
        )
        self.assertEqual(result.value.files, ("ambiguous.h", "complete.c"))

    def test_single_file_uses_parent_as_root(self) -> None:
        source = FIXTURE / "complete.cpp"
        result = CppWorkspaceCollector().collect(make_context(source))
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual(result.value.root, source.parent.resolve())
        self.assertEqual(result.value.files, ("complete.cpp",))

    def test_unsupported_single_file_and_missing_input_are_structured(self) -> None:
        unsupported = CppWorkspaceCollector().collect(make_context(FIXTURE / "notes.txt"))
        missing = CppWorkspaceCollector().collect(make_context(FIXTURE / "absent.cpp"))
        self.assertEqual(unsupported.status, CompletionStatus.UNAVAILABLE)
        self.assertEqual(unsupported.diagnostics[0].code, "workspace.unsupported-input")
        self.assertEqual(missing.status, CompletionStatus.FAILED)
        self.assertEqual(missing.diagnostics[0].code, "workspace.input-missing")

    def test_external_symlink_is_skipped_without_absolute_identity_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURE, project)
            outside = Path(tmp) / "outside.c"
            outside.write_text("int outside(void) { return 0; }\n", encoding="utf-8")
            (project / "escape.c").symlink_to(outside)
            result = CppWorkspaceCollector().collect(make_context(project, excludes=("generated",)))
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertNotIn("escape.c", result.value.files)
        self.assertEqual(result.diagnostics[0].code, "workspace.path-escape")
        self.assertNotIn(tmp, result.diagnostics[0].message)


if __name__ == "__main__":
    unittest.main()
