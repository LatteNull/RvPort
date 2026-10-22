from __future__ import annotations

import json
import platform
import resource
import time
import unittest

import networkx

from kb_scanner.core import Entity, Relation, stable_id
from kb_scanner.graph import NetworkXGraphStore


class EvidenceGraphBenchmarkTests(unittest.TestCase):
    def test_synthetic_graph_stays_inside_container_budget(self) -> None:
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        started = time.perf_counter()
        store = NetworkXGraphStore()
        entities = [Entity(stable_id("benchmark-entity", index), "node", str(index)) for index in range(1_000)]
        for entity in entities:
            store.add_entity(entity)
        for index in range(3_000):
            source = entities[index % 1_000]
            target = entities[(index + 1) % 1_000]
            store.add_relation(
                Relation(stable_id("benchmark-relation", index), "references", source.id, target.id, status="complete")
            )
        search = store.search_paths(
            entities[0].id,
            entities[500].id,
            max_depth=8,
            max_visited=10_000,
            max_paths=4,
        )
        elapsed = time.perf_counter() - started
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_delta_mib = max(0, rss_after - rss_before) / 1024
        self.assertEqual((store.entity_count, store.relation_count), (1_000, 3_000))
        self.assertIn(search.status, {"partial", "not_found", "complete"})
        self.assertLess(elapsed, 15.0)
        self.assertLess(rss_delta_mib, 512.0)
        print(
            "evidence-graph synthetic benchmark: "
            + json.dumps(
                {
                    "pythonVersion": platform.python_version(),
                    "networkxVersion": networkx.__version__,
                    "entities": store.entity_count,
                    "relations": store.relation_count,
                    "maxDepth": 8,
                    "maxVisited": 10_000,
                    "maxPaths": 4,
                    "seconds": round(elapsed, 6),
                    "peakRssDeltaMiB": round(rss_delta_mib, 3),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
