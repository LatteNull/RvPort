"""Isolated coverage of retained legacy helpers, not a legacy pipeline scan."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_scanner import cpp_frontend as frontend
from kb_scanner.compile_commands import load_compile_commands
from kb_scanner.models import CompileCommandContext, FileFacts, IncludeFact


class HistoricalFrontendTests(unittest.TestCase):
    def test_compile_database_tokens_errors_and_missing_input(self):
        path = Path("/p/compile_commands.json")
        rows = [None, {}, {"file": "a.c", "arguments": ["cc", "-I", "inc", "-Iother", "-D", "ZERO=0", "-DONE", "-std=c11", "-D", "-I"]},
                {"file": "/p/b.c", "command": "cc -DX=1 -c b.c"}, {"file": "c.c"}, {"file": "bad.c", "command": "'"}]
        with patch.object(Path, "read_text", return_value=json.dumps(rows)):
            contexts, errors = load_compile_commands(path)
        self.assertEqual(3, len(contexts))
        self.assertEqual(3, len(errors))
        self.assertEqual(["inc", "other"], contexts["/p/a.c"].include_dirs)
        self.assertEqual("0", contexts["/p/a.c"].defines["ZERO"])
        self.assertIsNone(contexts["/p/a.c"].defines["ONE"])
        self.assertEqual("c11", contexts["/p/a.c"].language_standard)
        self.assertEqual(({}, []), load_compile_commands(None))
        for value in ("{", "{}"):
            with patch.object(Path, "read_text", return_value=value):
                self.assertTrue(load_compile_commands(path)[1])
        with patch.object(Path, "read_text", side_effect=OSError("gone")):
            self.assertTrue(load_compile_commands(path)[1])

    def test_parse_file_preprocessor_macros_and_error_paths(self):
        text = '\n'.join(['#else', '#endif', '#elif __riscv', '#endif', '#ifdef __AVX__', '#include <immintrin.h>',
                          '#define WRAP(x) _mm_add_ps(x)', '#define EMPTY(x)', '#define OBJECT _mm_setzero_ps()',
                          'WRAP(x); EMPTY(x); OBJECT(); if (x) plain();', '#elif __riscv', '#include "portable.h"',
                          '#else', 'generic();', '#endif', '#if defined(GENERIC)', 'scalar();', '#endif'])
        with patch.object(Path, "read_text", return_value=text):
            result = frontend.parse_file(Path("/p/a.c"), "syntax")
        self.assertEqual([True, False], [i.system for i in result.includes])
        expanded = [c for c in result.calls if c.via_macro]
        self.assertEqual(["_mm_add_ps"], [c.name for c in expanded])
        self.assertEqual("WRAP", expanded[0].via_macro)
        self.assertEqual(18, len(result.texts))
        self.assertTrue(result.branch_groups)
        with patch.object(Path, "read_text", side_effect=OSError("bad")):
            self.assertTrue(frontend.parse_file(Path("a.c"), "syntax").diagnostics)
            self.assertTrue(frontend.parse_rpm_spec_file(Path("a.spec"), "syntax").diagnostics)
        with patch.object(frontend, "parse_rpm_spec_file", return_value=result) as parse:
            self.assertIs(result, frontend.parse_file(Path("a.spec"), "syntax"))
            parse.assert_called_once()

    def test_rpm_parser_only_collects_text_and_metadata(self):
        text = '\n'.join(['%else', '%endif', 'ExclusiveArch: x86_64 %{ix86}', '%global optflags -mavx',
                          '%ifarch x86_64', '%build', 'echo build', '%else', 'echo fallback', '%endif',
                          '%if 1', 'x', '%endif', '%changelog', '# comment'])
        with patch.object(Path, "read_text", return_value=text):
            result = frontend.parse_rpm_spec_file(Path("a.spec"), "static")
        self.assertEqual(["x86_64", "%{ix86}"], result.texts[2].metadata["archTokens"])
        self.assertEqual("optflags", result.texts[3].metadata["rpmMacro"])
        self.assertEqual("build", result.texts[6].metadata["section"])
        self.assertTrue(result.texts[-1].metadata["changelog"])
        self.assertEqual([], result.calls)

    def test_branch_roles_and_macro_tokens(self):
        for kind, expression, expected in [("else", "x", "fallback_branch"), ("ifndef", "__AVX__", "fallback_branch"),
            ("ifndef", "X", "unknown"), ("ifnarch", "x86_64", "fallback_branch"), ("ifnarch", "X", "unknown"),
            ("if", "__riscv", "riscv_branch"), ("if", "__AVX__", "x86_branch"), ("if", "GENERIC", "generic_branch"), ("if", "X", "unknown")]:
            self.assertEqual(expected, frontend._branch_role(kind, expression))
        self.assertIsNone(frontend._first_macro("123 if"))
        self.assertEqual("X", frontend._first_macro("defined(X)"))

    def test_discovery_and_project_delegate_boundaries(self):
        root = Path("/p")
        paths = [root / p for p in ("a.c", "b.hpp", "c.S", "Makefile", "a.spec", "skip/a.c", "readme.txt", "folder")]
        with patch.object(Path, "rglob", return_value=paths), patch.object(Path, "is_file", lambda p: p != root and p.name != "folder"):
            selected = frontend.discover_cpp_files(root, ["skip"], ["/p/b.hpp"])
            self.assertEqual(sorted(paths[:1] + paths[2:5]), selected)
        with patch.object(Path, "is_file", return_value=True):
            self.assertEqual([paths[0]], frontend.discover_cpp_files(paths[0], []))
            self.assertEqual([], frontend.discover_cpp_files(paths[6], []))
            self.assertEqual([], frontend.discover_cpp_files(paths[0], [], ["a.c"]))
        fake = FileFacts(paths[0])
        with patch.object(frontend, "discover_cpp_files", return_value=[paths[0]]), patch.object(frontend, "parse_file", return_value=fake), patch.object(frontend, "_compile_reachable_files", return_value=set()):
            result = frontend.parse_project(root, [], [], "syntax", {})
        self.assertEqual([fake], result.files)

    def test_include_reachability_cycle_missing_and_system_include(self):
        root = Path("/p")
        a, h = root / "a.c", root / "include/h.h"
        a_facts = FileFacts(a, includes=[IncludeFact("h.h", a, 1, False), IncludeFact("missing.h", a, 2, False), IncludeFact("system.h", a, 3, True)])
        h_facts = FileFacts(h, includes=[IncludeFact("a.c", h, 1, False)])
        context = CompileCommandContext(a, include_dirs=["include", "/p/include"])
        self.assertEqual({str(a), str(h)}, frontend._compile_reachable_files(root, [a_facts, h_facts], {str(a): context, "/missing": context}))
        self.assertEqual(set(), frontend._compile_reachable_files(root, [a_facts], {}))
        self.assertIsNone(frontend._resolve_project_include("none", a, context, root, {}))
        reached = set()
        frontend._mark_compile_reachable(a, context, {}, reached, root)
        self.assertEqual(set(), reached)
