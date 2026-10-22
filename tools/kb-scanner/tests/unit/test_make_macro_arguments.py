from __future__ import annotations

import unittest

from kb_scanner.frontends.build.macro_arguments import parse_macro_recipes


def parse(text, **limits):
    return parse_macro_recipes(text, "Makefile", **limits)


class MakeMacroArgumentsTests(unittest.TestCase):
    def test_recursive_assignment_append_order_and_exact_spans(self):
        text = "BASE = -DUSE=0\nCPPFLAGS = $(BASE)\nCPPFLAGS += -D OTHER=2 -UUSE\nx.o: x.cpp\n\t$(CXX) $(CPPFLAGS) -c x.cpp -o x.o\n"
        records = parse(text)
        arguments = [r for r in records if r.kind == "build_argument"]
        self.assertEqual(["-DUSE=0", "-D OTHER=2", "-UUSE"], [r.value for r in arguments])
        self.assertEqual([0, 1, 2], [r.metadata["sourceChain"]["order"] for r in arguments])
        self.assertEqual((2, 5), arguments[0].metadata["sourceChain"]["viaLines"])
        for record in arguments:
            self.assertEqual(record.value, text.splitlines()[record.line - 1][record.start_column - 1:record.end_column - 1])
        self.assertTrue(records[-1].metadata["sourceChain"]["proven"])
        self.assertEqual("x.cpp", records[-1].metadata["sourceChain"]["source"])

    def test_forward_reference_and_immediate_assignment(self):
        for operator, expected in (("=", True), (":=", False)):
            records = parse(f"FLAGS {operator} $(LATER)\nLATER = -DX\nx.o: x.c\n\tcc $(FLAGS) -c x.c\n")
            self.assertEqual(expected, records[-1].metadata["sourceChain"]["proven"])
        records = parse("A = -DX=0\nB := $(A)\nA = -DX=1\nA ?= -DY\nA += -UZ\nx.o: x.c\n\tgcc $(B) $(A) -c x.c\n")
        self.assertEqual(["0", "1", "1"], [r.metadata["sourceChain"]["value"] for r in records if r.kind == 'build_argument'])

    def test_unknown_unused_other_target_and_noncompile_recipes(self):
        self.assertEqual((), parse("FLAGS = -DX\n"))
        for recipe in ("cc $(UNKNOWN) -c x.c", "cc -DX x.c", "cc -DX -c other.c", "cc -DX -c x.c y.c", "cc -DX -c $^", "cc -DX -c x.c && touch pwned", "cc @args -c x.c"):
            records = parse("x.o: x.c\n\t" + recipe + "\n")
            self.assertFalse(records[-1].metadata["sourceChain"]["proven"], recipe)
        self.assertEqual((), parse("x.o: x.c\n\tpython build.py\n"))
        self.assertEqual((), parse("\tcc -DX -c x.c\n"))

    def test_unsupported_constructs_cycles_and_limits(self):
        for assignment in ("A = $(A)", "A = $(B)\nB = $(A)", "A = $(shell pwned)", "A = -D\"X\"", "A = -DX\\", "A = ${A}", "A = -DX\ninclude other.mk", "A = -DX\n$(eval A=-UX)"):
            records = parse(assignment + "\nx.o: x.c\n\tcc $(A) -c x.c\n")
            self.assertFalse(records[-1].metadata["sourceChain"]["proven"], assignment)
        for limits in ({"max_tokens": 1}, {"max_expansions": 1}):
            records = parse("A = $(B)\nB = -DX\nx.o: x.c\n\tcc $(A) -c x.c\n", **limits)
            self.assertFalse(records[-1].metadata["sourceChain"]["proven"])

    def test_conditionally_modified_variable_cannot_prove_recipe(self):
        records = parse("# comment\nA = -DX\nifdef SOMETHING\nA += -UX\nendif\nA += -DY\nx.o: x.c\n\tcc $(A) -c x.c\n")
        self.assertFalse(records[-1].metadata["sourceChain"]["proven"])
        unknown = parse("ifdef X\nx.o: x.c\n\tcc -DX -c x.c\nendif\n")
        self.assertFalse(unknown[-1].metadata['sourceChain']['proven'])
        self.assertEqual('-DX', unknown[0].value)

    def test_invalid_macro_tokens_and_separated_undef(self):
        for flag in ("-D1BAD", "-UX=1", "-D", "-U"):
            records = parse(f"x.o: x.c\n\tcc -c x.c {flag}\n")
            self.assertFalse(records[-1].metadata["sourceChain"]["proven"])
        records = parse("F ?= -D X -U X\nx.o: x.c\n\t@${CC} ${F} -c x.c\n")
        self.assertTrue(records[-1].metadata["sourceChain"]["proven"])
        self.assertEqual(["-D X", "-U X"], [r.value for r in records if r.kind == 'build_argument'])

    def test_indented_assignment_and_uninterpreted_overrides_do_not_use_stale_values(self):
        records = parse("A = -DX\n  A = -UX\nx.o: x.c\n\tcc $(A) -c x.c\n")
        self.assertEqual(["-UX"], [r.value for r in records if r.kind == 'build_argument'])
        self.assertTrue(records[-1].metadata["sourceChain"]["proven"])
        for override in ("A != printf -UX", "x.o: A = -UX"):
            records = parse("A = -DX\n" + override + "\nx.o: x.c\n\tcc $(A) -c x.c\n")
            self.assertFalse(records[-1].metadata["sourceChain"]["proven"])
        split = parse("FLAG = -D\nVALUE = X\nx.o: x.c\n\tcc $(FLAG) $(VALUE) -c x.c\n")
        self.assertTrue(split[-1].metadata["sourceChain"]["proven"])
        self.assertEqual('X', split[0].metadata['sourceChain']['macro'])
        self.assertTrue(any(r.line == 2 and r.value == 'X' for r in split if r.kind == 'build_assignment'))
