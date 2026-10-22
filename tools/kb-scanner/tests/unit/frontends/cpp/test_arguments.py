from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import CompilationUnitContext
from kb_scanner.frontends.cpp.arguments import normalize_clang_arguments


class ClangArgumentPolicyTests(unittest.TestCase):
    def make_unit(self, root: Path, tokens: tuple[str, ...]) -> CompilationUnitContext:
        source = root / "src" / "a.cpp"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.touch()
        return CompilationUnitContext(path=source, tokens=tokens, directory=root / "build")

    def test_all_safe_families_are_retained_and_paths_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tokens = ("clang++", "-I", "inc", "-isystem", "sys", "-iquoteq", "-idirafterafter", "-D", "A=1", "-DB", "-U", "OLD", "-x", "c++", "-target", "riscv64", "--target=x86_64", "--sysroot", "sdk", "-isysroot", "sdk2", "-std=c++20", "-nostdinc", "-nostdinc++", "-pthread", "-fsyntax-only", "-m32", "-m64", "-march=x86-64", "-mcpu=x", "-mtune=x", "-mabi=lp64", "-mfpmath=sse", "-mfloat-abi=hard", "-mno-avx", "-msse4.2", "-mavx2")
            result = normalize_clang_arguments(self.make_unit(root, tokens), root)
            self.assertEqual(result.diagnostics, ())
            self.assertIn(str((root / "build" / "inc").resolve()), result.accepted)
            self.assertIn(f"-iquote{(root / 'build' / 'q').resolve()}", result.accepted)
            self.assertIn("-march=x86-64", result.accepted)
            self.assertNotIn("clang++", result.accepted)

    def test_unsafe_groups_unknowns_and_missing_values_are_rejected_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tokens = ("cc", "-Xclang", "load", "@args", "-fplugin=x", "-include-pch", "a.pch", "-fmodule-file=x", "-o", "out", "-MFdep", "-MD", "-save-temps", "-ftime-trace", "-Wl,x", "-Wa,x", "--offload=x", "-unknown", "-I")
            result = normalize_clang_arguments(self.make_unit(root, tokens), root)
            self.assertEqual(result.accepted, ())
            options = [item.details["option"] for item in result.diagnostics]
            self.assertEqual(options, ["-Xclang", "@args", "-fplugin", "-include-pch", "-fmodule-file", "-o", "-MFdep", "-MD", "-save-temps", "-ftime-trace", "-Wl,x", "-Wa,x", "--offload", "-unknown", "-I"])
            self.assertEqual(result.diagnostics[-1].code, "clang.argument-missing-value")

    def test_driver_inputs_operands_and_compile_flag_are_removed_from_mixed_input(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            result = normalize_clang_arguments(self.make_unit(root, ("clang", "-c", "src/a.c", "operand", "-DOK", "-o", "x.o", "-std=c11")), root)
            self.assertEqual(result.accepted, ("-DOK", "-std=c11"))
            self.assertEqual(len(result.diagnostics), 1)

    def test_absolute_and_joined_paths_are_normalized_without_leaking_rejected_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            absolute = root / "absolute"
            result = normalize_clang_arguments(self.make_unit(root, ("cc", f"-I{absolute}", "--sysroot=sdk", "-plugin", str(root / "secret.so"))), root)
            self.assertEqual(result.accepted, (f"-I{absolute.resolve()}", f"--sysroot={(root / 'build' / 'sdk').resolve()}"))
            diagnostic = result.diagnostics[0]
            self.assertNotIn("secret", diagnostic.message)
            self.assertEqual(set(diagnostic.details), {"compilationContextId", "option", "removedPairedValue"})


if __name__ == "__main__":
    unittest.main()
