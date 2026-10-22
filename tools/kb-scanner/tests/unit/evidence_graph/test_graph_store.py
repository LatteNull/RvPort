from __future__ import annotations

import unittest

from kb_scanner.core import Entity, Relation, stable_id
from kb_scanner.graph import NetworkXGraphStore


def entity(name: str) -> Entity:
    return Entity(stable_id("entity", name), "node", name)


def relation(source: Entity, target: Entity, kind: str = "flows", suffix: str = "") -> Relation:
    return Relation(stable_id("relation", source.id, target.id, kind, suffix), kind, source.id, target.id)


class NetworkXGraphStoreTests(unittest.TestCase):
    def test_entities_relations_parallel_edges_and_filters_are_domain_objects(self) -> None:
        store = NetworkXGraphStore()
        left, right = entity("left"), entity("right")
        store.add_entity(left)
        store.add_entity(right)
        first = relation(left, right, "calls")
        second = relation(left, right, "expands_to")
        store.add_relation(second)
        store.add_relation(first)
        store.add_relation(first)
        self.assertEqual(store.entity(left.id), left)
        self.assertIsNone(store.entity(stable_id("missing")))
        self.assertEqual(store.entity_count, 2)
        self.assertEqual(store.relation_count, 2)
        self.assertEqual(store.outgoing(left.id), (first, second))
        self.assertEqual(store.outgoing(left.id, "calls"), (first,))
        self.assertEqual(store.incoming(right.id, "expands_to"), (second,))
        self.assertEqual(store.outgoing(stable_id("missing")), ())
        self.assertEqual(store.incoming(stable_id("missing")), ())
        self.assertTrue(all(type(item) is Relation for item in store.outgoing(left.id)))

    def test_collisions_and_unknown_endpoints_are_rejected(self) -> None:
        store = NetworkXGraphStore()
        left, right = entity("left"), entity("right")
        store.add_entity(left)
        store.add_entity(left)
        with self.assertRaises(ValueError):
            store.add_entity(Entity(left.id, "other", "collision"))
        with self.assertRaises(ValueError):
            store.add_relation(relation(left, right))
        store.add_entity(right)
        edge = relation(left, right)
        store.add_relation(edge)
        with self.assertRaises(ValueError):
            store.add_relation(Relation(edge.id, "other", left.id, right.id))

    def test_path_search_handles_success_not_found_missing_and_bad_budgets(self) -> None:
        store = NetworkXGraphStore()
        nodes = [entity(str(index)) for index in range(4)]
        for item in nodes:
            store.add_entity(item)
        edges = [relation(nodes[index], nodes[index + 1]) for index in range(3)]
        for edge in edges:
            store.add_relation(edge)
        found = store.search_paths(nodes[0].id, nodes[3].id, max_depth=4, max_visited=10, max_paths=2)
        self.assertEqual(found.status, "complete")
        self.assertEqual(found.paths, (tuple(item.id for item in edges),))
        missing = store.search_paths(nodes[3].id, nodes[0].id, max_depth=4, max_visited=10, max_paths=2)
        self.assertEqual(missing.status, "not_found")
        unknown = store.search_paths(stable_id("missing"), nodes[0].id, max_depth=4, max_visited=10, max_paths=2)
        self.assertEqual((unknown.status, unknown.reason), ("unknown", "missing-endpoint"))
        for budgets in ((0, 1, 1), (1, 0, 1), (1, 1, 0)):
            with self.subTest(budgets=budgets), self.assertRaises(ValueError):
                store.search_paths(nodes[0].id, nodes[1].id, max_depth=budgets[0], max_visited=budgets[1], max_paths=budgets[2])

    def test_path_search_reports_depth_visited_cycle_and_path_count_limits(self) -> None:
        store = NetworkXGraphStore()
        source, a, b, target = (entity(name) for name in ("source", "a", "b", "target"))
        for item in (source, a, b, target):
            store.add_entity(item)
        for edge in (
            relation(source, a, suffix="one"),
            relation(source, b, suffix="two"),
            relation(a, target),
            relation(b, target),
            relation(a, source, suffix="cycle"),
        ):
            store.add_relation(edge)
        depth = store.search_paths(source.id, target.id, max_depth=1, max_visited=20, max_paths=4)
        self.assertEqual((depth.status, depth.truncated, depth.reason), ("partial", True, "max-depth"))
        visited = store.search_paths(source.id, target.id, max_depth=4, max_visited=1, max_paths=4)
        self.assertEqual((visited.status, visited.reason), ("partial", "max-visited"))
        limited = store.search_paths(source.id, target.id, max_depth=4, max_visited=20, max_paths=1)
        self.assertEqual(limited.status, "partial")
        self.assertIn("max-paths", limited.reason)
        self.assertEqual(len(limited.paths), 1)
        cycle_only = store.search_paths(a.id, b.id, max_depth=4, max_visited=20, max_paths=4)
        self.assertEqual(cycle_only.status, "partial")
        self.assertIn("cycle", cycle_only.reason)


if __name__ == "__main__":
    unittest.main()
