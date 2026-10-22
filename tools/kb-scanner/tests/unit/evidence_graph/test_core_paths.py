from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from kb_scanner.core import AnalysisSnapshot, Entity, PathSearchResult, ProofPath, Relation, stable_id


class CorePathTests(unittest.TestCase):
    def test_proof_path_and_snapshot_freeze_collections(self) -> None:
        source = stable_id("source")
        target = stable_id("target")
        relation_id = stable_id("relation")
        proof = ProofPath(stable_id("proof"), source, target, [relation_id], "partial", "ambiguous", 4, False)  # type: ignore[arg-type]
        entity = Entity(source, "source_file", "main.c")
        relation = Relation(relation_id, "calls", source, target)
        snapshot = AnalysisSnapshot([relation], [entity], [proof])  # type: ignore[arg-type]
        self.assertEqual(proof.relation_ids, (relation_id,))
        self.assertEqual((snapshot.entities, snapshot.relations, snapshot.proof_paths), ((entity,), (relation,), (proof,)))
        with self.assertRaises(FrozenInstanceError):
            proof.status = "complete"  # type: ignore[misc]

    def test_path_search_freezes_paths_and_supports_not_found(self) -> None:
        relation_id = stable_id("relation")
        result = PathSearchResult([[relation_id]], "partial", 7, True, "max-depth")  # type: ignore[arg-type]
        self.assertEqual(result.paths, ((relation_id,),))
        self.assertEqual(PathSearchResult(), PathSearchResult((), "not_found", 0, False, None))

    def test_invalid_references_statuses_and_counts_are_rejected(self) -> None:
        source = stable_id("source")
        target = stable_id("target")
        valid = dict(id=stable_id("proof"), source_id=source, target_id=target)
        cases = (
            {"id": "bad"},
            {"source_id": "bad"},
            {"target_id": "bad"},
            {"relation_ids": ("bad",)},
            {"status": "safe"},
            {"visited": -1},
            {"status": "complete", "truncated": True},
            {"reason": ""},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ProofPath(**(valid | changes))
        search_cases = (
            {"paths": (("bad",),)},
            {"status": "safe"},
            {"visited": -1},
            {"status": "complete", "truncated": True},
            {"reason": ""},
            {"status": "not_found", "paths": ((stable_id("r"),),)},
        )
        for changes in search_cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                PathSearchResult(**changes)


if __name__ == "__main__":
    unittest.main()
