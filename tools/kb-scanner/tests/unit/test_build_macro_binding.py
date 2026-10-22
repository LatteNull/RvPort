from dataclasses import replace
from types import SimpleNamespace as NS
import unittest

from kb_scanner.core import Entity, Evidence, NormalizedSnapshot, SourceLocation, SourceSpan, stable_id
from kb_scanner.analyzers.build_macro_binding import MacroState, bind_build_macros, evaluate_condition
from kb_scanner.frontends.build.macro_arguments import parse_macro_recipes
from kb_scanner.frontends.build.vocabulary import BuildInputKind, make_build_evidence


def ev(identifier, kind, value, line, end=None, subject="cpp", **metadata):
    if "macroDefinitionEvidenceId" in metadata:
        metadata["macroDefinitionEvidenceId"] = stable_id(metadata["macroDefinitionEvidenceId"])
    return Evidence(stable_id(identifier), kind, stable_id(subject), value, "fake", "fake", "high",
                    SourceSpan(SourceLocation("x.cpp" if subject == "cpp" else "h.h", line, 1),
                               SourceLocation("x.cpp" if subject == "cpp" else "h.h", end or line, 10)), metadata=metadata)


def facts(extra=(), flags="-DX=1", source="x.cpp", recipe=None):
    records = parse_macro_recipes(f"CPPFLAGS = {flags}\nx.o: {source}\n\t{recipe or ('c++ $(CPPFLAGS) -c ' + source)}\n", "Makefile")
    build = tuple(make_build_evidence(r, path="Makefile", subject_id=stable_id("make"), producer="fake", input_kind=BuildInputKind.MAKE) for r in records)
    entities = (Entity(stable_id("cpp"), "source_file", "x.cpp"), Entity(stable_id("header"), "source_file", "h.h"), Entity(stable_id("make"), "build_file", "Makefile"))
    return NormalizedSnapshot(entities, (*build, *extra))


class BuildMacroBindingTests(unittest.TestCase):
    def test_condition_values_definedness_and_unknown_are_distinct(self):
        for text, kind, macros, expected in (
            ("X", "preproc_ifdef", {"X": MacroState(True, "0", "x")}, True),
            ("X", "preproc_ifndef", {"X": MacroState(True, "0", "x")}, False),
            ("X", "preproc_if", {"X": MacroState(True, "0", "x")}, False),
            ("defined(X)", "preproc_if", {"X": MacroState(True, "0", "x")}, True),
            ("!defined X", "preproc_if", {"X": MacroState(False, None, "x")}, True),
            ("X == 0x10", "preproc_if", {"X": MacroState(True, "16", "x")}, True),
            ("X != -1", "preproc_if", {"X": MacroState(True, "-1", "x")}, False),
            ("X == 8", "preproc_if", {"X": MacroState(True, "010", "x")}, True),
            ("X", "preproc_if", {"X": MacroState(True, "08", "x")}, None),
            ("X", "preproc_if", {"X": MacroState(False, None, "x")}, False),
            ("X", "preproc_if", {"X": MacroState(None, None, "x")}, None),
            ("X", "preproc_if", {"X": MacroState(True, "other", "x")}, None),
            ("X", "preproc_ifdef", {}, None), ("defined(X)", "preproc_if", {}, None),
            ("X && Y", "preproc_if", {}, None), ("X", "preproc_if", {}, None)):
            with self.subTest(text=text, kind=kind, macros=macros):
                self.assertIs(expected, evaluate_condition(NS(value=text, metadata={"nodeType": kind}), macros)[1])

    def resolve(self, snapshot, limit=1000):
        entities, relations = {}, {}
        limited = bind_build_macros(snapshot, entities, relations, max_relations=limit)
        return entities, relations, limited

    def test_binding_proves_argument_recipe_condition_and_original_ids(self):
        condition = ev("condition", "preprocessor_condition", "defined(X)", 4, 6, nodeType="preproc_if")
        entities, relations, limited = self.resolve(facts((condition,)))
        self.assertFalse(limited)
        self.assertEqual(3, len(relations))
        self.assertEqual(1, sum(r.kind == 'defines' for r in relations.values()))
        self.assertTrue(all(r.status == "selected" for r in relations.values()))
        binding = next(r for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == condition.id)
        self.assertEqual("Makefile:x.o:3", binding.metadata["configuration"])
        self.assertEqual(3, len(binding.evidence_ids))

    def test_unused_other_source_unknown_recipe_and_missing_source_do_not_bind(self):
        condition = ev("condition", "preprocessor_condition", "X", 4, nodeType="preproc_ifdef")
        for snapshot in (facts((condition,), recipe="cc -c x.cpp"), facts((condition,), source="other.cpp"),
                         facts((condition,), recipe="cc $(UNKNOWN) -c x.cpp"), NormalizedSnapshot()):
            entities, relations, _ = self.resolve(snapshot)
            self.assertFalse(any(entities[r.target_id].properties["sourceEvidenceId"] == condition.id for r in relations.values()))

    def test_ordered_undef_and_zero_values(self):
        for flags, kind, expected in (("-DX=0", "preproc_ifdef", "selected"), ("-DX=0", "preproc_if", "inactive"),
                                      ("-DX=1 -UX", "preproc_ifdef", "inactive"), ("-UX -DX", "preproc_ifdef", "selected")):
            entities, relations, _ = self.resolve(facts((ev("condition", "preprocessor_condition", "X", 4, nodeType=kind),), flags=flags))
            binding = next(r for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition"))
            self.assertEqual(expected, binding.status)

    def test_source_define_undef_and_nested_unknown_override(self):
        condition = ev("condition", "preprocessor_condition", "X", 8, nodeType="preproc_if")
        undef = ev("undef", "macro_expansion", "#undef X", 2, macroUndefName="X")
        define = ev("define", "macro_definition", "X", 3)
        token = ev("token", "macro_replacement_token", "0", 3, macroDefinitionEvidenceId="define", ordinal=0)
        for extra in ((undef,), (define, token)):
            entities, relations, _ = self.resolve(facts((*extra, condition)))
            bound = [r for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")]
            self.assertEqual(2, len(bound))
            self.assertEqual({"inactive"}, {r.status for r in bound})
        outer = ev("outer", "preprocessor_condition", "UNRESOLVED", 1, 6, nodeType="preproc_if")
        entities, relations, _ = self.resolve(facts((outer, define, token, condition)))
        self.assertEqual({"unknown"}, {r.status for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")})

    def test_visible_local_include_and_unknown_external_include(self):
        condition = ev("condition", "preprocessor_condition", "X", 8, nodeType="preproc_ifdef")
        for include, expected in (("h.h", "inactive"), ("missing.h", "unknown"), ("../h.h", "unknown")):
            inc = ev("include", "include", include, 1)
            undef = ev("undef", "macro_expansion", "#undef X", 1, subject="header", macroUndefName="X")
            entities, relations, _ = self.resolve(facts((inc, undef, condition)))
            self.assertEqual({expected}, {r.status for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")})

    def test_budget_and_include_cycle_fail_conservatively(self):
        condition = ev("condition", "preprocessor_condition", "X", 8, nodeType="preproc_ifdef")
        self.assertTrue(self.resolve(facts((condition,)), 1)[2])
        inc = ev("inc", "include", "x.cpp", 1)
        entities, relations, limited = self.resolve(facts((inc, condition)))
        self.assertTrue(limited)
        self.assertEqual({"unknown"}, {r.status for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")})

    def test_inactive_branch_does_not_override_outer_state_and_partial_structure_is_unknown(self):
        outer = ev("outer", "preprocessor_condition", "X", 1, 5, nodeType="preproc_if")
        define = ev("define", "macro_definition", "X", 2)
        condition = ev("condition", "preprocessor_condition", "X", 8, nodeType="preproc_ifdef", structureComplete=False)
        entities, relations, _ = self.resolve(facts((outer, define, condition), flags="-DX=0"))
        self.assertEqual({"unknown"}, {r.status for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")})

    def test_alternative_join_is_unknown_instead_of_using_last_textual_define(self):
        branch = ev("else", "preprocessor_branch", "else", 2, 5)
        condition = ev("condition", "preprocessor_condition", "X", 8, nodeType="preproc_ifdef")
        entities, relations, _ = self.resolve(facts((branch, condition)))
        self.assertEqual({"unknown"}, {r.status for r in relations.values() if entities[r.target_id].properties["sourceEvidenceId"] == stable_id("condition")})
