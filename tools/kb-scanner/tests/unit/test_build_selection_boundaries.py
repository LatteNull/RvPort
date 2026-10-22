import unittest
from dataclasses import replace
from unittest.mock import patch

from kb_scanner.analyzers.build_selection import BuildSelectionAnalyzer, BuildProofBudgets, BuildSourceReachabilityResolver, _knowledge_matches
from kb_scanner.core import Entity, Relation, stable_id
from tests.unit.projection_reachability.test_build_reachability import fixture
from tests.unit.build_selection.support import context


class BuildSelectionBoundaryTests(unittest.TestCase):
    def test_ambiguous_source_and_relation_path_budgets(self):
        facts, knowledge = fixture()
        ambiguous = replace(facts, entities=(*facts.entities, Entity(stable_id("second-source"), "source_file", "src/foo.cpp")))
        result = BuildSelectionAnalyzer().analyze(context(), ambiguous, knowledge)
        self.assertFalse(any(r.kind == "uses_source" for r in result.value.relations))
        for limits in (BuildProofBudgets(max_relations=2), BuildProofBudgets(max_relations=3), BuildProofBudgets(max_paths=1)):
            result = BuildSelectionAnalyzer(limits).analyze(context(), facts, knowledge)
            self.assertFalse(any(r.metadata.get("itemKind") == "source_x86_dependency" for r in result.value.relations))
        with patch("kb_scanner.analyzers.build_macro_binding.bind_build_macros", return_value=True):
            result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        self.assertIn("build-selection.macro-budget", [d.code for d in result.diagnostics])

    def test_inactive_pattern_does_not_select_dependency_for_selected_target(self):
        facts, knowledge = fixture()
        facts = replace(facts, facts=tuple(replace(f, metadata={**f.metadata, "selectionStatus": "inactive"}) if f.kind == "build_source" else f for f in facts.facts))
        result = BuildSelectionAnalyzer().analyze(context(), facts, knowledge)
        self.assertEqual(["unknown"], [r.status for r in result.value.relations if r.kind == "uses_source"])

    def test_include_walk_preserves_paths_and_ignores_cycles_unknown_or_external_nodes(self):
        a, b, external = (Entity(stable_id(n), k, n) for n, k in (("a.c", "source_file"), ("b.h", "source_file"), ("external", "external_header")))
        edges = [(a, b, "complete"), (b, a, "complete"), (a, external, "complete"), (b, external, "unknown")]
        relations = {str(i): Relation(stable_id("r", i), "includes", source.id, target.id, (), status=state) for i, (source, target, state) in enumerate(edges)}
        relations["missing"] = Relation(stable_id("missing-r"), "includes", a.id, stable_id("absent"), ())
        output = BuildSourceReachabilityResolver._reachable_source_files(a, {x.id: x for x in (a, b, external)}, relations)
        by_id = {e.id: path for e, path in output}
        self.assertEqual({a.id, b.id}, set(by_id))
        self.assertEqual((relations["0"].id,), by_id[b.id])
        self.assertTrue(_knowledge_matches("asm eax", "eax", "inline_asm"))
        self.assertFalse(_knowledge_matches("eax_suffix", "eax", "inline_asm"))
        self.assertTrue(_knowledge_matches("-march=x86", "-march", "compiler_argument"))
        self.assertFalse(_knowledge_matches("-other", "-march", "compiler_argument"))

    def test_missing_target_entity_and_proof_never_invent_membership(self):
        facts, knowledge = fixture()
        initial = BuildSelectionAnalyzer().analyze(context(), facts, knowledge).value
        entities = {e.id: e for e in initial.entities}
        selector = next(e for e in initial.entities if e.kind == "architecture_selector")
        items = {e.properties["factId"]: e for e in initial.entities if "factId" in e.properties}
        for selected_items, proofs in (({}, {p.id: p for p in initial.proof_paths}), (items, {})):
            relations = {}
            BuildSourceReachabilityResolver(BuildProofBudgets()).resolve(context(), facts, knowledge, selector, entities, relations, proofs, selected_items)
            self.assertEqual({}, relations)
