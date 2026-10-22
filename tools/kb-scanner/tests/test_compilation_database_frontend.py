from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.frontends.cpp import CompilationDatabaseReader, compilation_context_id


def write_database(root: Path, entries: object) -> Path:
    path = root / "compile_commands.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


class CompilationDatabaseReaderTests(unittest.TestCase):
    def test_arguments_and_command_entries_preserve_duplicate_source_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src" / "main.cpp"
            source.parent.mkdir()
            source.write_text("int main() { return 0; }\n", encoding="utf-8")
            database = write_database(
                root,
                [
                    {
                        "directory": str(root),
                        "file": "src/main.cpp",
                        "arguments": ["clang++", "-Iinclude", "-D", "MODE=one", "-std=c++20", "src/main.cpp"],
                    },
                    {
                        "directory": ".",
                        "file": "src/main.cpp",
                        "command": "g++ -isystem vendor/include -DMODE=two -std=gnu++23 src/main.cpp",
                    },
                ],
            )
            result = CompilationDatabaseReader().read(database, root)
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual(len(result.value), 2)
        self.assertEqual(result.value[0].compiler, "clang++")
        self.assertEqual(result.value[0].defines, (("MODE", "one"),))
        self.assertEqual(result.value[0].include_dirs, ("include",))
        self.assertEqual(result.value[1].compiler, "g++")
        self.assertEqual(result.value[1].include_dirs, ("vendor/include",))
        self.assertEqual(result.value[1].language_standard, "gnu++23")
        self.assertNotEqual(
            compilation_context_id(result.value[0], root),
            compilation_context_id(result.value[1], root),
        )

    def test_partial_entries_and_paths_outside_project_are_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            source = root / "valid.c"
            source.write_text("int valid;\n", encoding="utf-8")
            database = write_database(
                root,
                [
                    {"directory": str(root), "file": "valid.c", "arguments": ["clang", "valid.c"]},
                    {"directory": str(root), "arguments": ["clang", "missing.c"]},
                    {"directory": str(root), "file": "valid.c", "command": "clang 'unterminated"},
                    {"directory": str(root), "file": "../outside.c", "arguments": ["clang", "../outside.c"]},
                ],
            )
            result = CompilationDatabaseReader().read(database, root)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(len(result.value), 1)
        self.assertEqual(
            {item.code for item in result.diagnostics},
            {
                "compilation-database.missing-file",
                "compilation-database.invalid-command",
                "compilation-database.source-outside-workspace",
            },
        )

    def test_missing_invalid_and_fully_invalid_databases_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = CompilationDatabaseReader().read(root / "missing.json", root)
            invalid = root / "invalid.json"
            invalid.write_text("{", encoding="utf-8")
            invalid_result = CompilationDatabaseReader().read(invalid, root)
            all_bad = write_database(root, [{"arguments": ["clang"]}])
            all_bad_result = CompilationDatabaseReader().read(all_bad, root)
        self.assertEqual(missing.status, CompletionStatus.UNAVAILABLE)
        self.assertEqual(invalid_result.status, CompletionStatus.UNAVAILABLE)
        self.assertEqual(all_bad_result.status, CompletionStatus.UNAVAILABLE)
        self.assertIsNone(all_bad_result.value)

    def test_context_identity_is_stable_across_machine_roots(self) -> None:
        identities = []
        root_names = []
        for _ in range(2):
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name)
            root_names.append(root.as_posix())
            source = root / "src" / "same.cpp"
            source.parent.mkdir()
            source.write_text("int same;\n", encoding="utf-8")
            database = write_database(
                root,
                [{
                    "directory": str(root),
                    "file": str(source),
                    "arguments": ["clang++", f"-I{root / 'include'}", "-DVALUE=1", "-std=c++20", str(source)],
                }],
            )
            unit = CompilationDatabaseReader().read(database, root).value[0]
            identities.append(compilation_context_id(unit, root))
        self.assertEqual(identities[0], identities[1])
        self.assertFalse(any(name in identity for name in root_names for identity in identities))

    def test_reader_never_executes_command_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            marker = root / "must-not-exist"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            database = write_database(
                root,
                [{"directory": str(root), "file": "main.c", "command": f"clang main.c ; touch {marker}"}],
            )
            result = CompilationDatabaseReader().read(database, root)
            self.assertFalse(marker.exists())
        self.assertEqual(result.status, CompletionStatus.COMPLETE)


if __name__ == "__main__":
    unittest.main()
