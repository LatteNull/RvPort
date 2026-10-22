from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompilationUnitContext, CompletionStatus
from kb_scanner.frontends.cpp.compilation_database import CompilationDatabaseReader, compilation_context_id
from tests.unit.frontends.cpp.support import write_json


class CompilationDatabaseTests(unittest.TestCase):
    def test_missing_invalid_json_and_non_array_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            reader = CompilationDatabaseReader()
            self.assertEqual(reader.read(None, root).status, CompletionStatus.UNAVAILABLE)
            bad = root / "bad.json"
            bad.write_text("{", encoding="utf-8")
            self.assertEqual(reader.read(bad, root).diagnostics[0].code, "compilation-database.invalid-json")
            shaped = write_json(root / "shape.json", {})
            self.assertEqual(reader.read(shaped, root).diagnostics[0].code, "compilation-database.invalid-shape")

    def test_entry_validation_partial_valid_and_all_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.c").write_text("", encoding="utf-8")
            database = write_json(root / "compile_commands.json", [None, {"file": 2}, {"file": "a.c", "arguments": ["cc", {"bad": 1}]}, {"file": "a.c", "arguments": ["cc", "-c", "a.c"]}])
            result = CompilationDatabaseReader().read(database, root)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertEqual(len(result.value), 1)
            self.assertEqual([d.code for d in result.diagnostics], ["compilation-database.missing-file", "compilation-database.missing-file", "compilation-database.invalid-command"])
            invalid = write_json(root / "invalid.json", [{"directory": "."}])
            self.assertEqual(CompilationDatabaseReader().read(invalid, root).status, CompletionStatus.UNAVAILABLE)

    def test_command_tokenization_empty_command_and_outside_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root, outside = Path(raw), Path(outside_raw)
            (root / "a.c").write_text("", encoding="utf-8")
            database = write_json(root / "compile_commands.json", [
                {"file": "a.c", "command": "cc 'unterminated"},
                {"file": "a.c", "command": ""},
                {"file": str(outside / "x.c"), "arguments": ["cc"]},
            ])
            result = CompilationDatabaseReader().read(database, root)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertEqual(result.value[0].tokens, ())
            self.assertEqual([d.code for d in result.diagnostics], ["compilation-database.invalid-command", "compilation-database.source-outside-workspace"])

    def test_parses_paths_includes_defines_standard_compiler_and_multiple_entries(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "src").mkdir()
            (root / "src" / "a.cpp").write_text("", encoding="utf-8")
            args = ["C:\\LLVM\\bin\\clang++.exe", "-I", "inc", "-isystemsys", "-iquotequote", "-idirafter", "after", "-D", "A=1", "-DA=2", "-DB", "-std=c++20", "src/a.cpp"]
            database = write_json(root / "compile_commands.json", [
                {"directory": ".", "file": "src/a.cpp", "arguments": args},
                {"directory": str(root), "file": str(root / "src" / "a.cpp"), "command": "cc -D C=3 src/a.cpp"},
            ])
            result = CompilationDatabaseReader().read(database, root)
            self.assertEqual(result.status, CompletionStatus.COMPLETE)
            self.assertEqual([unit.entry_index for unit in result.value], [0, 1])
            first = result.value[0]
            self.assertEqual(first.include_dirs, ("inc", "sys", "quote", "after"))
            self.assertEqual(first.defines, (("A", "2"), ("B", None)))
            self.assertEqual(first.language_standard, "c++20")
            self.assertEqual(first.compiler, "clang++.exe")
            self.assertEqual(first.tokens, tuple(args))

    def test_context_identity_tracks_semantics_but_redacts_machine_roots(self) -> None:
        with tempfile.TemporaryDirectory() as left_raw, tempfile.TemporaryDirectory() as right_raw:
            left, right = Path(left_raw), Path(right_raw)
            for root in (left, right):
                (root / "src").mkdir()
                (root / "src" / "a.c").write_text("", encoding="utf-8")
            def unit(root: Path, entry: int = 0, define: str = "1"):
                return CompilationUnitContext(path=root / "src" / "a.c", defines=(("A", define),), language_standard="c11", tokens=("cc", f"-I{root.as_posix()}/inc", "-I/opt/vendor"), entry_index=entry, directory=root)
            self.assertEqual(compilation_context_id(unit(left), left), compilation_context_id(unit(right), right))
            self.assertNotEqual(compilation_context_id(unit(left), left), compilation_context_id(unit(left, entry=1), left))
            self.assertNotEqual(compilation_context_id(unit(left), left), compilation_context_id(unit(left, define="2"), left))


if __name__ == "__main__":
    unittest.main()
