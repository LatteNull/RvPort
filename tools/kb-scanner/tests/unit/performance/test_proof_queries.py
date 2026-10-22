from dataclasses import replace
import random
import unittest
from unittest.mock import Mock, patch

from kb_scanner.analyzers.proof import ProofPathResolver, ProofBudgets
from kb_scanner.core import Relation, stable_id
from kb_scanner.graph import NetworkXGraphStore
from kb_scanner.graph.queries import plan_queries
from tests.unit.evidence_graph.test_graph_store import entity, relation


class SearchOnly:
    """No query planning: original all-pairs resolver oracle."""
    def __init__(self, store):
        self.search_paths = store.search_paths


class ProofQueryTests(unittest.TestCase):
    def test_planner_keeps_mid_path_evidence_depth_and_parallel_edges(self):
        nodes = [entity(str(i)) for i in range(4)]
        requested = stable_id("requested")
        edges = tuple(replace(relation(nodes[i], nodes[i+1]), evidence_ids=(requested,) if i == 1 else ()) for i in range(3))
        sources, targets = (nodes[0].id,), (nodes[3].id,)
        self.assertEqual({sources[0]: targets}, plan_queries(sources, targets, edges, 3, {requested}))
        self.assertEqual({}, plan_queries(sources, targets, edges, 2, {requested}))
        self.assertEqual({}, plan_queries(sources, targets, edges, 3, set()))
        self.assertEqual({sources[0]: targets}, plan_queries(sources, targets, edges, 3))
        with self.assertRaises(ValueError):
            plan_queries(sources, targets, edges, 0)

    def test_differential_all_fields_cycles_parallel_edges_and_budgets(self):
        randomizer = random.Random(41)
        requested = stable_id("requested")
        for graph_number in range(20):
            store = NetworkXGraphStore()
            nodes = [entity(str(i)) for i in range(5)]
            for node in nodes:
                store.add_entity(node)
            edges = []
            for i in range(14):
                left, right = randomizer.choices(nodes, k=2)
                edge = replace(relation(left, right, suffix=str(i)),
                               evidence_ids=(requested,) if i % 3 == 0 else (),
                               status="partial" if i % 4 == 0 else "complete",
                               metadata={"reason": "incomplete"} if i % 4 == 0 else {})
                edges.append(edge)
                store.add_relation(edge)
            ids = tuple(n.id for n in nodes)
            for budgets in (ProofBudgets(1, 1, 1), ProofBudgets(3, 7, 2), ProofBudgets(8, 100, 4)):
                for demand in (None, frozenset((requested,))):
                    with self.subTest(graph=graph_number, budgets=budgets, demand=demand):
                        expected = ProofPathResolver(SearchOnly(store), budgets).resolve(ids, ids, tuple(edges), required_evidence_ids=demand)
                        actual = ProofPathResolver(store, budgets).resolve(ids, ids, tuple(edges), required_evidence_ids=demand)
                        self.assertEqual(expected, actual)

    def test_empty_demand_does_not_search_and_store_plan_can_be_unavailable(self):
        store = Mock()
        self.assertEqual((), ProofPathResolver(store).resolve((), (), (), required_evidence_ids=frozenset()))
        store.search_paths.assert_not_called()
        from kb_scanner.core import PathSearchResult
        store.plan_queries.return_value = None
        store.search_paths.return_value = PathSearchResult()
        self.assertEqual((), ProofPathResolver(store).resolve((stable_id("a"),), (stable_id("b"),), ()))
        store.search_paths.assert_called_once()

    def test_sparse_query_count_and_cache_invalidation_across_graph_updates(self):
        store = NetworkXGraphStore()
        nodes = [entity(str(i)) for i in range(100)]
        for node in nodes:
            store.add_entity(node)
        edge = relation(nodes[0], nodes[1])
        store.add_relation(edge)
        first = store.outgoing(nodes[0].id)
        self.assertIs(first, store.outgoing(nodes[0].id))
        search = Mock(wraps=store.search_paths)
        class Planned:
            plan_queries = store.plan_queries
            search_paths = search
        ids = tuple(node.id for node in nodes)
        ProofPathResolver(Planned()).resolve(ids[:50], ids[50:], (edge,))
        self.assertEqual(0, search.call_count)
        extra = relation(nodes[0], nodes[99])
        store.add_relation(extra)
        self.assertEqual(2, len(store.outgoing(nodes[0].id)))
        ProofPathResolver(Planned()).resolve(ids[:50], ids[50:], (edge, extra))
        self.assertEqual(1, search.call_count)
        self.assertEqual((), NetworkXGraphStore().outgoing(nodes[0].id))
