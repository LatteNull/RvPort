from __future__ import annotations

import unittest

from kb_scanner.frontends.build.safety import normalize_target_arch, symbolic_uname, unsafe_constructs
from kb_scanner.frontends.build.vocabulary import (
    BuildInputKind,
    BuildRecord,
    SelectionStatus,
    make_build_evidence,
    make_build_file_entity,
    record_for_token,
)
from kb_scanner.frontends.build.workspace import build_input_kind, is_build_input


class VocabularySafetyTests(unittest.TestCase):
    def test_input_kinds_statuses_and_routing_are_explicit(self) -> None:
        expected = {
            "Makefile": BuildInputKind.MAKE,
            "rules.mk": BuildInputKind.MAKE,
            "configure": BuildInputKind.SHELL,
            "config.sub": BuildInputKind.SHELL,
            "configure.ac": BuildInputKind.M4,
            "macros/x.m4": BuildInputKind.M4,
            ".cmake/api/v1/reply/index.json": BuildInputKind.CMAKE,
            "meson-info/intro-targets.json": BuildInputKind.MESON,
            "ctest-v1.json": BuildInputKind.CTEST,
            "CTestTestfile.cmake": BuildInputKind.CTEST,
            "compile_commands.json": BuildInputKind.COMPILATION_DATABASE,
            "demo.spec": BuildInputKind.RPM,
        }
        for path, kind in expected.items():
            with self.subTest(path=path):
                self.assertEqual(build_input_kind(path), kind)
                self.assertTrue(is_build_input(path))
        self.assertEqual(BuildInputKind.CMAKE_SOURCE, build_input_kind("CMakeLists.txt"))
        self.assertFalse(is_build_input("main.c"))
        self.assertEqual({item.value for item in SelectionStatus}, {"selected", "inactive", "not_selected", "unknown"})

    def test_records_entities_and_evidence_are_stable_and_validated(self) -> None:
        entity = make_build_file_entity("config/Makefile", BuildInputKind.MAKE, "1")
        record = record_for_token("build_argument", "-mavx", 2, "CFLAGS += -mavx", metadata={"selectionStatus": "selected"})
        evidence = make_build_evidence(record, path=entity.name, subject_id=entity.id, producer="unit", input_kind=BuildInputKind.MAKE)
        self.assertEqual(entity, make_build_file_entity("config/Makefile", BuildInputKind.MAKE, "1"))
        self.assertEqual(evidence, make_build_evidence(record, path=entity.name, subject_id=entity.id, producer="unit", input_kind=BuildInputKind.MAKE))
        self.assertEqual((evidence.location.start.column, evidence.location.end.column), (11, 16))
        with self.assertRaises(ValueError):
            BuildRecord("bad", "x", 1, 1, 2)
        for args in (("build_target", "", 1, 1, 2), ("build_target", "x", 0, 1, 2), ("build_target", "x", 1, 2, 1)):
            with self.assertRaises(ValueError):
                BuildRecord(*args)
        with self.assertRaises(ValueError):
            BuildRecord("build_target", "x", 1, 1, 2, confidence="certain")
        with self.assertRaises(ValueError):
            make_build_file_entity("../escape", BuildInputKind.MAKE, "1")

    def test_uname_is_narrow_symbolic_probe_and_unsafe_constructs_are_retained(self) -> None:
        for command in ("uname -m", "$(uname -m)", "`uname -m`", "$(shell uname -m)"):
            result = symbolic_uname(command, "riscv64-linux")
            self.assertTrue(result.recognized, command)
            self.assertEqual(result.value, "riscv64")
        self.assertEqual(normalize_target_arch("rv32"), "riscv32")
        self.assertEqual(normalize_target_arch("risc-v"), "riscv64")
        with self.assertRaises(ValueError):
            normalize_target_arch("x86_64")
        for command in ("env X=1 uname -m", "uname -m | cat", "uname -m > out", "sh -c 'uname -m'", "uname -p"):
            self.assertFalse(symbolic_uname(command, "riscv64").recognized, command)
        make = "ARCH := $(shell uname -m)\nX := $(shell touch marker)\nY != id\nZ := $(eval bad)\nW := $(wildcard *)\n"
        names = {item[0] for item in unsafe_constructs(make, "make")}
        self.assertEqual(names, {"shell-function", "shell-assignment", "eval-function", "dynamic-function"})
        self.assertEqual({item[0] for item in unsafe_constructs("m4_syscmd(x)\nesyscmd(y)\ninclude(z)", "m4")}, {"m4-syscmd", "m4-esyscmd", "m4-include"})
        self.assertEqual({item[0] for item in unsafe_constructs("execute_process(COMMAND x)", "cmake")}, {"cmake-execute-process"})
        self.assertEqual({item[0] for item in unsafe_constructs("%(x)\n%{lua:x}\n%include y", "rpm")}, {"rpm-shell-expansion", "rpm-lua-expansion", "rpm-include"})
        self.assertEqual(unsafe_constructs("plain", "unknown"), ())


if __name__ == "__main__":
    unittest.main()
