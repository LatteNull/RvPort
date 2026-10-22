from __future__ import annotations

import unittest

from kb_scanner.analyzers import ProofBudgets, ProofPathResolver
from kb_scanner.core import PathSearchResult, Relation, stable_id


class FakeStore:
    def __init__(self, result: PathSearchResult) -> None:
        self.result = result
        self.calls = []

    def search_paths(self, source_id, target_id, **budgets):
        self.calls.append((source_id, target_id, budgets))
        return self.result


class ProofPathResolverTests(unittest.TestCase):
    def test_budgets_require_positive_values(self) -> None:
        for values in ((0, 1, 1), (1, 0, 1), (1, 1, 0)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ProofBudgets(*values)

    def test_complete_and_partial_paths_preserve_order_and_reasons(self) -> None:
        source, middle, target = (stable_id(name) for name in ("source", "middle", "target"))
        first = Relation(stable_id("r1"), "flows", source, middle, status="complete")
        second = Relation(stable_id("r2"), "flows", middle, target, status="partial", metadata={"reason": "ambiguous"})
        complete_store = FakeStore(PathSearchResult(((first.id,),), "complete", 2))
        complete = ProofPathResolver(complete_store).resolve((source,), (middle,), (first,))
        self.assertEqual(complete[0].status, "complete")
        self.assertEqual(complete_store.calls[0][2], {"max_depth": 8, "max_visited": 10000, "max_paths": 4})

        partial_store = FakeStore(PathSearchResult(((first.id, second.id),), "partial", 5, True, "max-depth"))
        partial = ProofPathResolver(partial_store, ProofBudgets(2, 6, 1)).resolve((source,), (target,), (first, second))
        self.assertEqual((partial[0].status, partial[0].truncated), ("partial", True))
        self.assertEqual(partial[0].reason, "ambiguous,max-depth")
        self.assertEqual(partial[0].relation_ids, (first.id, second.id))

    def test_no_paths_produces_no_materialized_proof_and_inputs_are_deduplicated(self) -> None:
        source, target = stable_id("source"), stable_id("target")
        store = FakeStore(PathSearchResult(status="not_found", visited=1))
        result = ProofPathResolver(store).resolve((source, source), (target, target), ())
        self.assertEqual(result, ())
        self.assertEqual(len(store.calls), 1)

    def test_missing_relation_marks_materialized_path_partial(self) -> None:
        source, target, missing = stable_id("source"), stable_id("target"), stable_id("missing")
        store = FakeStore(PathSearchResult(((missing,),), "complete", 1))
        proof = ProofPathResolver(store).resolve((source,), (target,), ())[0]
        self.assertEqual(proof.status, "partial")
        self.assertEqual(proof.reason, "missing-relation")


if __name__ == "__main__":
    unittest.main()
