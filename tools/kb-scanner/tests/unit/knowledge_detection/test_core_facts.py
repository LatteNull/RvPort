from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from kb_scanner.core import NormalizedFact, stable_id


class CoreFactTests(unittest.TestCase):
    def test_fact_is_frozen_and_deduplicates_provenance(self) -> None:
        evidence_a = stable_id("evidence", "a")
        evidence_b = stable_id("evidence", "b")
        context = stable_id("context", "a")
        fact = NormalizedFact(
            stable_id("fact"), "symbol", stable_id("subject"), "_mm_add_ps", "source:main.c:1",
            (evidence_b, evidence_a, evidence_b), (context, context), ("tree", "clang", "tree"), {"ok": [1]},
        )
        self.assertEqual(fact.evidence_ids, tuple(sorted((evidence_a, evidence_b))))
        self.assertEqual(fact.context_ids, (context,))
        self.assertEqual(fact.producers, ("clang", "tree"))
        with self.assertRaises(FrozenInstanceError):
            fact.kind = "x"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            fact.metadata["x"] = 1  # type: ignore[index]

    def test_fact_rejects_invalid_fields_references_and_metadata(self) -> None:
        valid = dict(
            id=stable_id("fact"), kind="symbol", subject_id=stable_id("subject"), canonical_value="x",
            scope="source:a", evidence_ids=(stable_id("evidence"),),
        )
        cases = (
            {"id": "bad"}, {"kind": ""}, {"subject_id": "bad"}, {"canonical_value": ""},
            {"scope": ""}, {"evidence_ids": ()}, {"evidence_ids": ("bad",)},
            {"context_ids": ("bad",)}, {"metadata": {"bad": object()}},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                NormalizedFact(**(valid | changes))


if __name__ == "__main__":
    unittest.main()
