from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompilationUnitContext
from kb_scanner.frontends.cpp import normalize_clang_arguments


ROOT = Path(__file__).resolve().parents[1]
UNSAFE_FIXTURE = ROOT / "tests" / "fixtures" / "formal-cpp-frontend" / "unsafe-arguments.json"


class ClangArgumentPolicyTests(unittest.TestCase):
    def test_mixed_arguments_keep_only_audited_parse_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src" / "main.cpp"
            source.parent.mkdir()
            source.write_text("int main() { return 0; }\n", encoding="utf-8")
            tokens = tuple(json.loads(UNSAFE_FIXTURE.read_text(encoding="utf-8")))
            unit = CompilationUnitContext(path=source, tokens=tokens, entry_index=7, directory=root)
            result = normalize_clang_arguments(unit, root)

        self.assertEqual(
            result.accepted,
            (
                f"-I{root / 'include'}",
                "-isystem",
                str(root / "vendor" / "include"),
                "-DARCH=x86",
                "-std=c++20",
                "-mavx2",
            ),
        )
        rejected = {item.details["option"] for item in result.diagnostics}
        self.assertTrue(
            {
                "-Xclang",
                "-fplugin",
                "@arguments.rsp",
                "-include-pch",
                "-fmodule-map-file",
                "-o",
                "-MF",
                "-ftime-trace",
                "-Wl,-plugin,linker.so",
            }.issubset(rejected)
        )
        self.assertTrue(all(item.details["compilationContextId"] for item in result.diagnostics))
        self.assertFalse(any(tmp in item.message for item in result.diagnostics))

    def test_paired_and_joined_paths_normalize_against_command_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            unit = CompilationUnitContext(
                path=source,
                tokens=(
                    "clang",
                    "-I",
                    "include",
                    "-iquotequoted",
                    "-idirafter",
                    "after",
                    "--sysroot=sysroot",
                    "--target=riscv64-linux-gnu",
                    "-x",
                    "c",
                    "main.c",
                ),
                directory=root,
            )
            result = normalize_clang_arguments(unit, root)
        self.assertEqual(
            result.accepted,
            (
                "-I",
                str(root / "include"),
                f"-iquote{root / 'quoted'}",
                "-idirafter",
                str(root / "after"),
                f"--sysroot={root / 'sysroot'}",
                "--target=riscv64-linux-gnu",
                "-x",
                "c",
            ),
        )
        self.assertEqual(result.diagnostics, ())

    def test_unknown_target_and_driver_groups_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.cpp"
            source.write_text("int main() { return 0; }\n", encoding="utf-8")
            unit = CompilationUnitContext(
                path=source,
                tokens=(
                    "clang++",
                    "-mllvm",
                    "dangerous-backend-option",
                    "-Xassembler",
                    "plugin-input",
                    "--offload-arch=gfx90a",
                    "-save-temps=obj",
                    "-unknown",
                    "main.cpp",
                ),
                directory=root,
            )
            marker = root / "dangerous-backend-option"
            result = normalize_clang_arguments(unit, root)
            self.assertFalse(marker.exists())
        self.assertEqual(result.accepted, ())
        self.assertEqual(
            {item.details["option"] for item in result.diagnostics},
            {"-mllvm", "-Xassembler", "--offload-arch", "-save-temps", "-unknown"},
        )

    def test_missing_safe_value_is_reported_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("int main(void);\n", encoding="utf-8")
            unit = CompilationUnitContext(path=source, tokens=("clang", "-I"), directory=root)
            result = normalize_clang_arguments(unit, root)
        self.assertEqual(result.accepted, ())
        self.assertEqual(result.diagnostics[0].code, "clang.argument-missing-value")


if __name__ == "__main__":
    unittest.main()
