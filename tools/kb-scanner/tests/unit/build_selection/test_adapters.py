from __future__ import annotations

import json
import unittest

from kb_scanner.frontends.build.adapters import parse_m4, parse_machine_json, parse_rpm, parse_shell


class AdapterTests(unittest.TestCase):
    def test_shell_recovers_uname_branches_and_rejects_other_commands(self) -> None:
        result = parse_shell("machine=$(uname -m)\ncase $machine in\nriscv64) x=1 ;;\nx86_64) x=2 ;;\n*) x=3 ;;\nesac\ny=$(touch marker)\n", "configure", "riscv64")
        self.assertTrue(result.partial)
        self.assertTrue(any(item.kind == "build_arch_probe" for item in result.records))
        statuses = {(item.metadata["role"], item.metadata["selectionStatus"]) for item in result.records if item.kind == "build_branch"}
        self.assertTrue({("riscv", "selected"), ("x86", "inactive"), ("generic", "selected")} <= statuses)
        self.assertTrue(any(item.kind == "build_unsupported" for item in result.records))

    def test_m4_is_allowlisted_and_never_evaluated(self) -> None:
        result = parse_m4("dnl comment\nAC_CANONICAL_HOST()\nAS_CASE([$host], [riscv64], [ok])\nUNKNOWN_MACRO([x])\nm4_syscmd([touch marker])\n", "configure.ac", "riscv64")
        self.assertTrue(result.partial)
        self.assertTrue(any(item.kind == "build_condition" and item.metadata["role"] == "riscv" for item in result.records))
        self.assertGreaterEqual(sum(item.kind == "build_unsupported" for item in result.records), 2)

    def test_machine_readers_cover_cmake_meson_ctest_compile_database_and_errors(self) -> None:
        cmake = {"name": "riscv64", "targets": [{"name": "app", "type": "test", "suite": "unit", "coverageTarget": "src/a.c", "tested_source": "src/b.c", "callTarget": "portable_api", "alternativeTestFor": "other-test", "sources": [{"path": "src/a.c"}], "compile_args": ["-mavx -Wall"], "dependencies": [{"id": "dep"}], "artifacts": [{"path": "out/app"}]}]}
        result = parse_machine_json(json.dumps(cmake), "reply.json", "cmake", "riscv64")
        self.assertFalse(result.partial)
        self.assertEqual({item.kind for item in result.records}, {"build_configuration", "build_target", "build_source", "build_argument", "build_dependency", "build_artifact"})
        self.assertTrue(all(item.metadata["selectionStatus"] == "selected" for item in result.records))
        target = next(item for item in result.records if item.kind == "build_target")
        self.assertEqual(target.metadata["testRole"], "confirmed")
        self.assertEqual(target.metadata["testSuite"], "unit")
        self.assertEqual(target.metadata["coverageTarget"], "src/a.c")
        self.assertEqual(target.metadata["testedSource"], "src/b.c")
        self.assertEqual(target.metadata["callTarget"], "portable_api")
        self.assertEqual(target.metadata["alternativeTestFor"], "other-test")
        meson = parse_machine_json('[{"name":"x86-app","sources":["x.c"],"compile_parameters":["-mavx"]}]', "intro-targets.json", "meson", "riscv64")
        self.assertTrue(all(item.metadata["selectionStatus"] == "inactive" for item in meson.records))
        ctest = parse_machine_json('{"tests":[{"name":"t","command":"run","sources":["t.c"]}]}', "ctest.json", "ctest", "riscv64")
        self.assertTrue(any(item.kind == "build_target" for item in ctest.records))
        self.assertTrue(all(item.metadata.get("testRole") == "confirmed" for item in ctest.records if item.kind == "build_target"))
        compile_db = parse_machine_json('[{"file":"main.c","arguments":["clang","--target=riscv64","-mavx"]}]', "compile_commands.json", "compilation-database", "riscv64")
        self.assertTrue(any(item.kind == "build_argument" and item.value == "-mavx" for item in compile_db.records))
        invalid = parse_machine_json("{", "bad.json", "cmake", "riscv64")
        self.assertTrue(invalid.partial)
        too_large = parse_machine_json(" " * (4 * 1024 * 1024 + 1), "big.json", "cmake", "riscv64")
        self.assertTrue(too_large.partial)
        malformed = parse_machine_json('["bad"]', "bad.json", "meson", "riscv64")
        self.assertTrue(malformed.partial)
        self.assertTrue(any("not an object" in item for item in malformed.diagnostics))

    def test_rpm_selection_constraints_and_unsafe_macros(self) -> None:
        from unittest.mock import patch
        from kb_scanner.frontends.build.vocabulary import BuildRecord
        record = BuildRecord('build_dependency', 'foo', 2, 1, 4, {'selectionStatus':'unknown'})
        with patch('kb_scanner.frontends.build.rpm.parser.parse', return_value=((record,), ('partial',))) as parser:
            result = parse_rpm('Requires: foo', 'demo.spec', 'riscv64')
        parser.assert_called_once_with('Requires: foo', 'demo.spec', 'riscv64')
        self.assertEqual((record,), result.records)
        self.assertEqual(('partial',), result.diagnostics)
        self.assertTrue(result.partial)


if __name__ == "__main__":
    unittest.main()
