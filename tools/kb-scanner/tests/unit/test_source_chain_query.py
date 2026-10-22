import unittest
from types import SimpleNamespace as NS

from kb_scanner.projection.v2.source_chain import Arc, SourceChainIndex, primary_path


def evidence(kind="call_expression", **metadata):
    return NS(kind=kind, metadata=metadata, location=True)


def snapshot(eids, edges, *, kinds=None, configs=None, structural=()):
    items = {eid: evidence((kinds or {}).get(eid, "call_expression")) for eid in eids}
    entities = {eid: NS(properties={"sourceEvidenceId": eid}) for eid in eids}
    entities.update({nid: NS(properties={}) for nid in structural})
    relations = {str(i): NS(id=str(i), source_id=a, target_id=b, kind=k, evidence_ids=tuple(extra),
                           metadata={"configuration": (configs or {}).get(str(i))})
                 for i, (a, b, k, extra) in enumerate(edges)}
    return NS(evidence=items, entities=entities, relations=relations, facts={})


class SourceChainQueryTests(unittest.TestCase):
    def test_shared_macro_header_does_not_pull_in_including_sibling_translation_units(self):
        graph = snapshot(('call','definition','arg','include-one','include-two'),
                         [('call','definition','expands_to',('call','definition')),
                          ('definition','arg','expands_to',('definition','arg')),
                          ('one','header','includes',('include-one',)),
                          ('two','header','includes',('include-two',)),
                          ('header','definition','defines',())],
                         kinds={'include-one':'include','include-two':'include'},
                         configs={'0':'one-config','1':'one-config'},structural=('one','two','header'))
        graph.evidence['arg'].metadata['callEvidenceId']='call'
        for key,item in graph.evidence.items():
            item.location=NS(start=NS(path='shared.h' if key=='definition' else 'two.cpp' if key=='include-two' else 'one.cpp'))
        for key in ('0','1'):
            graph.relations[key].metadata['macroEffect']={'invocationId':'call','translationUnit':'one.cpp'}
        query=SourceChainIndex(graph).query('arg',configuration='one-config')
        self.assertEqual((),query.reasons)
        self.assertIn('include-one',query.evidence_ids)
        self.assertNotIn('include-two',query.evidence_ids)
        self.assertEqual(('call','definition','arg'),primary_path('arg',query.arcs))

    def test_macro_actual_filters_other_invocation_and_unscoped_expansion(self):
        graph = snapshot('abcd', [('a','c','expands_to',()),('b','c','expands_to',()),('d','c','calls',())])
        graph.evidence['c'] = evidence('macro_argument_token', callEvidenceId='call-one')
        graph.relations['0'].metadata['macroEffect'] = {'invocationId':'call-one'}
        graph.relations['1'].metadata['macroEffect'] = {'invocationId':'call-two'}
        query = SourceChainIndex(graph).query('c')
        self.assertEqual(('a','c'),query.evidence_ids)
        self.assertEqual((Arc('a','c','expands_to',('0',)),),query.arcs)

    def test_upstream_and_expansion_keep_all_same_kind_layers(self):
        graph = snapshot("abcde", [("a", "b", "guarded_by", ()), ("a", "c", "invokes_macro", ()),
                                  ("c", "d", "expands_to", ()), ("d", "e", "expands_to", ())])
        query = SourceChainIndex(graph).query("a")
        self.assertEqual(tuple("abcde"), query.evidence_ids)
        self.assertEqual(tuple("bacde"), primary_path("a", query.arcs))
        self.assertEqual((), query.reasons)
        self.assertEqual(5, query.visited)

    def test_macro_replacement_retains_its_own_location_and_terminal_is_not_global_symbol_join(self):
        graph = snapshot("abxy", [("a", "s", "expands_to", ("b",)), ("x", "s", "calls", ("y",))],
                         kinds={"b": "macro_replacement_token"}, structural=("s",))
        query = SourceChainIndex(graph).query("b")
        self.assertEqual(("a", "b"), query.evidence_ids)
        self.assertEqual((Arc("a", "b", "expands_to", ("0",)),), query.arcs)

    def test_structural_collapse_preserves_continuous_relation_sequence(self):
        graph = snapshot("ab", [("a", "middle", "selects", ()), ("middle", "b", "defines", ())], structural=("middle",))
        query = SourceChainIndex(graph).query("b")
        self.assertEqual((Arc("a", "b", "selects", ("0", "1")),), query.arcs)
        self.assertEqual(("a", "b"), primary_path("b", query.arcs))

    def test_fact_backed_endpoint_and_include_occurrence(self):
        graph = snapshot("abi", [("a", "file", "includes", ("i",)), ("file", "b", "defines", ())],
                         kinds={"i": "include"}, structural=("file",))
        graph.entities["a"] = NS(properties={"factId": "fact"})
        graph.facts["fact"] = NS(evidence_ids=("a",))
        query = SourceChainIndex(graph).query("b")
        self.assertEqual(("a", "b", "i"), query.evidence_ids)
        self.assertEqual(("a", "i", "b"), primary_path("b", query.arcs))

    def test_unrelated_growth_does_not_change_result_or_visit_count(self):
        edges = [("a", "b", "calls", ())]
        small = SourceChainIndex(snapshot(("a", "b"), edges)).query("b")
        nodes = tuple(str(i) for i in range(1000))
        large = SourceChainIndex(snapshot(("a", "b", *nodes), edges + [(str(i), str(i + 1), "calls", ()) for i in range(999)])).query("b")
        self.assertEqual(small, large)

    def test_configuration_filter_does_not_cross_other_target(self):
        graph = snapshot("abc", [("a", "c", "selects", ()), ("b", "c", "selects", ())], configs={"0": "one", "1": "two"})
        index = SourceChainIndex(graph)
        self.assertEqual(("a", "c"), index.query("c", configuration="one").evidence_ids)
        self.assertEqual(("a", "b", "c"), index.query("c").evidence_ids)
        self.assertEqual(("a", "b", "c"), index.query("c", configuration="default").evidence_ids)

    def test_recipe_only_follows_argument_origin_used_by_current_binding(self):
        graph = snapshot("abcd", [("a", "c", "selects", ()), ("b", "c", "selects", ()), ("c", "d", "selects", ("a", "c", "d"))])
        graph.evidence["c"] = evidence(sourceChain={"role": "recipe"})
        self.assertEqual(("a", "c", "d"), SourceChainIndex(graph).query("d").evidence_ids)

    def test_unresolved_endpoints_are_not_given_a_borrowed_source(self):
        graph = snapshot("ab", [("missing", "a", "selects", ("b",)), ("b", "b", "uses", ())])
        query = SourceChainIndex(graph).query("a")
        self.assertEqual(("a",), query.evidence_ids)
        self.assertEqual((), query.arcs)
        self.assertIn("missing_reference", query.reasons)
        self.assertEqual(("a",), primary_path("a", query.arcs))

    def test_limits_and_deterministic_order(self):
        graph = snapshot("abcd", [("a", "b", "calls", ()), ("b", "c", "calls", ()), ("c", "d", "calls", ())])
        index = SourceChainIndex(graph)
        for options in ({"max_visited": 1}, {"max_depth": 1}, {"max_paths": 1}):
            query = index.query("d", **options)
            self.assertIn("reference_budget_exceeded", query.reasons)
            self.assertIn("d", primary_path("d", query.arcs, **{k:v for k,v in options.items() if k != "max_visited"}))
        reference = index.query("d")
        graph.relations = dict(reversed(list(graph.relations.items())))
        graph.entities = dict(reversed(list(graph.entities.items())))
        self.assertEqual(reference, SourceChainIndex(graph).query("d"))
        for options in ({"max_depth": 0}, {"max_visited": 0}, {"max_paths": 0}):
            with self.assertRaises(ValueError):
                index.query("d", **options)
        with self.assertRaises(ValueError):
            index.query("missing")

    def test_structural_cycle_is_bounded_and_reported(self):
        graph = snapshot("a", [("x", "a", "selects", ()), ("y", "x", "defines", ()), ("x", "y", "defines", ())], structural=("x", "y"))
        query = SourceChainIndex(graph).query("a")
        self.assertIn("cycle_detected", query.reasons)
        self.assertEqual(3, query.visited)

    def test_self_edges_and_multiple_paths_never_invent_an_edge(self):
        graph = snapshot("abc", [("a", "a", "defines", ()), ("a", "c", "calls", ()), ("b", "c", "calls", ())])
        query = SourceChainIndex(graph).query("c")
        path = primary_path("c", query.arcs)
        self.assertEqual(("a", "c"), path)
        self.assertNotIn(Arc("a", "b", "contains", ()), query.arcs)
