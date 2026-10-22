from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompilationUnitContext, CompletionStatus, ScanContext, WorkspaceSnapshot
from kb_scanner.frontends.cpp import ClangCppAdapter, compilation_context_id, make_source_file_entity


ROOT = Path(__file__).resolve().parents[1]


def make_context(root: Path, units: tuple[CompilationUnitContext, ...]) -> ScanContext:
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
        compile_commands_path=root / "compile_commands.json",
        compile_contexts=units,
        scan_mode="compile_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="riscv-porting@1",
        scanner_name="kb-scanner",
        scanner_version="0.1.0",
    )


def project_fixture(root: Path) -> tuple[Path, Path]:
    header = root / "config.h"
    source = root / "main.c"
    header.write_text("#define SCALE(value) ((value) * 2)\n", encoding="utf-8")
    source.write_text(
        '#include "config.h"\n#define LOCAL(value) SCALE(value)\n'
        "int helper(int value) { return value; }\n"
        "int run(int value) { return LOCAL(value) + helper(value); }\n",
        encoding="utf-8",
    )
    return source, header


def make_unit(root: Path, source: Path, entry_index: int, mode: str = "one") -> CompilationUnitContext:
    return CompilationUnitContext(
        path=source,
        tokens=("clang", "-I", str(root), f"-DMODE={mode}", "-std=c17", str(source)),
        entry_index=entry_index,
        compiler="clang",
        directory=root,
    )


class ClangCppAdapterTests(unittest.TestCase):
    def test_preprocessing_and_semantic_evidence_is_project_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _ = project_fixture(root)
            unit = make_unit(root, source, 0)
            workspace = WorkspaceSnapshot(root, ("config.h", "main.c"))
            entities = {
                path: make_source_file_entity(path, ("c", "cpp"), "0.1.0") for path in workspace.files
            }
            result = ClangCppAdapter().enrich(make_context(root, (unit,)), workspace, unit, entities)
        kinds = {item.kind for item in result.value}
        self.assertTrue(
            {
                "macro_definition",
                "macro_parameter",
                "macro_replacement_token",
                "macro_expansion",
                "include",
                "call_expression",
            }.issubset(kinds),
            kinds,
        )
        definition_ids = {item.id for item in result.value if item.kind == "macro_definition"}
        attachments = [item for item in result.value if item.kind in {"macro_parameter", "macro_replacement_token"}]
        self.assertTrue(attachments)
        self.assertTrue(all(item.metadata["macroDefinitionEvidenceId"] in definition_ids for item in attachments))
        scale = next(
            item
            for item in attachments
            if item.kind == "macro_replacement_token" and item.value == "SCALE"
        )
        self.assertEqual(scale.metadata["tokenRole"], "call_candidate")
        self.assertTrue(all(item.location.start.path in workspace.files for item in result.value))
        self.assertTrue(all(item.producer == "clang@18.1.3" for item in result.value))
        self.assertTrue(all(item.parse_mode == "clang_enrichment" for item in result.value))
        self.assertTrue(all(item.metadata["compilationContextId"] == compilation_context_id(unit, root) for item in result.value))

    def test_two_entries_keep_independent_provenance_and_stable_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _ = project_fixture(root)
            units = (make_unit(root, source, 0, "one"), make_unit(root, source, 1, "two"))
            workspace = WorkspaceSnapshot(root, ("config.h", "main.c"))
            entities = {
                path: make_source_file_entity(path, ("c", "cpp"), "0.1.0") for path in workspace.files
            }
            adapter = ClangCppAdapter()
            first = adapter.enrich(make_context(root, units), workspace, units[0], entities)
            repeated = adapter.enrich(make_context(root, units), workspace, units[0], entities)
            second = adapter.enrich(make_context(root, units), workspace, units[1], entities)
        self.assertEqual(first, repeated)
        self.assertNotEqual(
            {item.metadata["compilationContextId"] for item in first.value},
            {item.metadata["compilationContextId"] for item in second.value},
        )
        comparable_first = {(item.kind, item.value, item.location) for item in first.value}
        comparable_second = {(item.kind, item.value, item.location) for item in second.value}
        self.assertTrue(comparable_first & comparable_second)
        self.assertFalse({item.id for item in first.value} & {item.id for item in second.value})
        self.assertEqual(len(first.value), len({item.id for item in first.value}))

    def test_missing_include_is_partial_and_keeps_available_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "broken.c"
            source.write_text('#include "absent.h"\n#define LOCAL 1\nint value = LOCAL;\n', encoding="utf-8")
            unit = make_unit(root, source, 0)
            workspace = WorkspaceSnapshot(root, ("broken.c",))
            entities = {"broken.c": make_source_file_entity("broken.c", ("c",), "0.1.0")}
            result = ClangCppAdapter().enrich(make_context(root, (unit,)), workspace, unit, entities)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertTrue(result.value)
        self.assertIn("clang.parse-diagnostic", {item.code for item in result.diagnostics})
        self.assertIn("macro_definition", {item.kind for item in result.value})

    def test_workspace_external_cursor_locations_are_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "project"
            external = base / "external"
            root.mkdir()
            external.mkdir()
            (external / "external.h").write_text("#define EXTERNAL_MACRO 7\n", encoding="utf-8")
            source = root / "main.c"
            source.write_text("#include <external.h>\nint value = EXTERNAL_MACRO;\n", encoding="utf-8")
            unit = CompilationUnitContext(
                path=source,
                tokens=("clang", "-I", str(external), str(source)),
                entry_index=0,
                compiler="clang",
                directory=root,
            )
            workspace = WorkspaceSnapshot(root, ("main.c",))
            entities = {"main.c": make_source_file_entity("main.c", ("c",), "0.1.0")}
            result = ClangCppAdapter().enrich(make_context(root, (unit,)), workspace, unit, entities)
        self.assertTrue(result.value)
        self.assertTrue(all(item.location.start.path == "main.c" for item in result.value))
        self.assertFalse(any(item.value == "EXTERNAL_MACRO" and item.kind == "macro_definition" for item in result.value))
        self.assertIn("include", {item.kind for item in result.value})

    def test_rejected_response_plugin_and_output_arguments_have_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            response = root / "unsafe.rsp"
            output = root / "marker.o"
            dependency = root / "marker.d"
            trace = root / "main.json"
            source.write_text("#ifdef RESPONSE_ONLY\nint response_loaded;\n#endif\nint main(void) { return 0; }\n", encoding="utf-8")
            response.write_text("-DRESPONSE_ONLY=1\n", encoding="utf-8")
            unit = CompilationUnitContext(
                path=source,
                tokens=(
                    "clang",
                    f"@{response}",
                    "-fplugin=missing-plugin.so",
                    "-Xclang",
                    "-load",
                    "-include-pch",
                    "missing.pch",
                    "-fmodule-map-file=missing.modulemap",
                    "-o",
                    str(output),
                    "-MF",
                    str(dependency),
                    "-ftime-trace",
                    str(source),
                ),
                directory=root,
            )
            workspace = WorkspaceSnapshot(root, ("main.c",))
            entities = {"main.c": make_source_file_entity("main.c", ("c",), "0.1.0")}
            result = ClangCppAdapter().enrich(make_context(root, (unit,)), workspace, unit, entities)
            self.assertFalse(output.exists())
            self.assertFalse(dependency.exists())
            self.assertFalse(trace.exists())
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertNotIn("RESPONSE_ONLY", {item.value for item in result.value if item.kind == "macro_definition"})
        self.assertIn("clang.argument-rejected", {item.code for item in result.diagnostics})


if __name__ == "__main__":
    unittest.main()
