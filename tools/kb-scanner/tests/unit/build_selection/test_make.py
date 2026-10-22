from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.frontends.build.make import MakeBudgets, MakeValue, parse_make, resolve_make_includes


class MakeTests(unittest.TestCase):
    def test_riscv_condition_uname_assignments_targets_and_flags(self) -> None:
        source = """ARCH := $(shell uname -m)
ifeq ($(ARCH),riscv64)
SRC := src/rv.c
CFLAGS += -march=rv64gc -mavx
else
SRC := src/generic.c
endif
all: $(SRC)
\t@touch marker
"""
        result = parse_make(source, "Makefile", "riscv64")
        self.assertFalse(result.partial, result.diagnostics)
        records = result.records
        self.assertEqual(next(item for item in records if item.kind == "build_arch_probe").metadata["resolvedValue"], "riscv64")
        sources = {(item.value, item.metadata["selectionStatus"]) for item in records if item.kind == "build_source"}
        self.assertIn(("src/rv.c", "selected"), sources)
        self.assertIn(("src/generic.c", "inactive"), sources)
        self.assertIn(("-mavx", "selected"), {(item.value, item.metadata["selectionStatus"]) for item in records if item.kind == "build_argument"})
        self.assertTrue(any(item.kind == "build_target" and item.value == "all" for item in records))
        self.assertFalse(any(item.value == "touch" for item in records))

    def test_assignments_unknowns_and_condition_edges(self) -> None:
        source = """A = one
A += two
A ?= ignored
B := $(MISSING)
C := $(wildcard *.c)
D != uname -m
ifdef A
X := yes
endif
ifndef MISSING
Y := yes
else extra
Y := no
endif
ifneq (riscv64,x86_64)
Z := yes
endif
else
endif
"""
        result = parse_make(source, "rules.mk", "riscv64", MakeBudgets(max_expansions=20))
        variables = dict(result.variables)
        self.assertEqual(variables["A"].text, "one two")
        self.assertEqual(variables["D"].text, "riscv64")
        self.assertEqual(variables["B"].kind, "unknown")
        self.assertTrue(result.partial)
        self.assertTrue(any("unmatched else" in item for item in result.diagnostics))
        self.assertTrue(any(item.kind == "build_unsupported" for item in result.records))

    def test_values_and_budgets_validate(self) -> None:
        self.assertEqual(MakeValue("alternatives", ("b", "a", "a")).values, ("a", "b"))
        self.assertEqual(MakeValue("list", ("a", "b")).text, "a b")
        self.assertIsNone(MakeValue("unknown", reason="x").text)
        for value in (MakeValue,):
            with self.assertRaises(ValueError):
                value("bad", ("x",))
        with self.assertRaises(ValueError):
            MakeValue("unknown")
        with self.assertRaises(ValueError):
            MakeValue("scalar")
        with self.assertRaises(ValueError):
            MakeBudgets(max_files=0)
        limited = parse_make("A := one two\n", "Makefile", "riscv64", MakeBudgets(max_candidates=1))
        self.assertEqual(dict(limited.variables)["A"].reason, "max-candidates")

    def test_include_resolver_is_bounded_and_workspace_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payloads = {
                str((root / "Makefile").resolve()): "include a.mk\n",
                str((root / "a.mk").resolve()): "include Makefile\nA := yes\n",
            }

            def loader(path: Path) -> str:
                return payloads[str(path)]

            result = resolve_make_includes("Makefile", root, loader, "riscv64")
            self.assertTrue(result.partial)
            self.assertTrue(any("cycle" in item for item in result.diagnostics))
            budget = resolve_make_includes("Makefile", root, loader, "riscv64", MakeBudgets(max_files=1))
            self.assertTrue(any("budget" in item for item in budget.diagnostics))
            dynamic = {str((root / "Makefile").resolve()): "include $(X)\n"}
            result = resolve_make_includes("Makefile", root, lambda path: dynamic[str(path)], "riscv64")
            self.assertTrue(any("dynamic include" in item for item in result.diagnostics))
            missing = resolve_make_includes("missing.mk", root, lambda path: (_ for _ in ()).throw(OSError("missing")), "riscv64")
            self.assertTrue(any("unreadable" in item for item in missing.diagnostics))
            escape = resolve_make_includes("../outside.mk", root, loader, "riscv64")
            self.assertTrue(any("escapes" in item for item in escape.diagnostics))


if __name__ == "__main__":
    unittest.main()
