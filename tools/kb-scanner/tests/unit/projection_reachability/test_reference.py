from __future__ import annotations

import unittest

from kb_scanner.core import Entity, Evidence, ProofPath, Relation, SourceLocation, SourceSpan, stable_id
from kb_scanner.projection.reference import ReferenceClosureResolver, resolve_symbol


def span(path: str, start: int, end: int) -> SourceSpan:
    return SourceSpan(SourceLocation(path, 1, start), SourceLocation(path, 1, end))


class ReferenceClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Entity(stable_id("source"), "source_file", "a.c")
        self.definition_evidence = Evidence(stable_id("definition-evidence"), "macro_definition", self.source.id, "M", "unit", "ast", "high", span("a.c", 1, 5))
        self.definition = Entity(stable_id("definition"), "macro_definition", "M", properties={"sourceEvidenceId": self.definition_evidence.id})
        self.call_evidence = Evidence(stable_id("call-evidence"), "call_expression", self.source.id, "M", "unit", "ast", "high", span("a.c", 10, 11))
        self.relation = Relation(stable_id("relation"), "invokes_macro", self.source.id, self.definition.id, (self.call_evidence.id,), "high", "complete")
        self.proof = ProofPath(stable_id("proof"), self.source.id, self.definition.id, (self.relation.id,), "complete", visited=2)

    def resolver(self, **kwargs) -> ReferenceClosureResolver:
        return ReferenceClosureResolver(
            {item.id: item for item in (self.definition_evidence, self.call_evidence)},
            {item.id: item for item in (self.source, self.definition)},
            {self.relation.id: self.relation},
            {self.proof.id: self.proof},
            **kwargs,
        )

    def test_closes_relation_proof_and_entity_source_evidence(self) -> None:
        result = self.resolver().resolve((self.call_evidence.id,), (), (self.proof.id,))
        self.assertEqual(result.status, "complete")
        self.assertEqual(set(result.evidence_ids), {self.call_evidence.id, self.definition_evidence.id})
        self.assertEqual(result.relation_ids, (self.relation.id,))

    def test_reports_missing_and_budget_truncation_deterministically(self) -> None:
        missing = self.resolver().resolve((), ("f" * 64,), ())
        self.assertEqual(missing.status, "partial")
        self.assertEqual(missing.missing_ids, ("f" * 64,))
        truncated = self.resolver(max_references=1).resolve((self.call_evidence.id,), (self.relation.id,), (self.proof.id,))
        self.assertTrue(truncated.truncated)
        self.assertEqual(("reference-budget-exceeded",), truncated.reasons)
        with self.assertRaises(ValueError):
            self.resolver(max_references=0)

    def test_type_conflicts_and_relation_cycles_are_bounded_and_order_independent(self) -> None:
        conflicting_entity = Entity(self.call_evidence.id, "symbol", "conflict")
        reverse = Relation(stable_id("reverse"), "returns_to", self.definition.id, self.source.id)
        resolver = ReferenceClosureResolver(
            {item.id: item for item in (self.call_evidence, self.definition_evidence)},
            {item.id: item for item in (self.source, self.definition, conflicting_entity)},
            {item.id: item for item in (reverse, self.relation)},
            {},
        )
        first = resolver.resolve((self.call_evidence.id,), (self.relation.id, reverse.id), ())
        second = resolver.resolve((self.call_evidence.id,), (reverse.id, self.relation.id), ())
        self.assertEqual(first, second)
        self.assertEqual("partial", first.status)
        self.assertEqual((self.call_evidence.id,), first.conflicting_ids)
        self.assertIn("reference-type-conflict", first.reasons)

    def test_symbol_resolution_uses_structured_values_then_knowledge_then_terminal(self) -> None:
        self.assertEqual("M", resolve_symbol(self.call_evidence, (), (), {self.source.id: self.source}))
        opaque = Evidence(stable_id("opaque"), "comment", self.source.id, "comment", "unit", "ast", "low")
        knowledge = type("Knowledge", (), {"canonical_value": "_mm_add_ps"})()
        self.assertEqual("_mm_add_ps", resolve_symbol(opaque, (knowledge,), (), {}))
        symbol = Entity(stable_id("symbol"), "symbol", "terminal")
        relation = Relation(stable_id("terminal-relation"), "calls", self.source.id, symbol.id)
        self.assertEqual("terminal", resolve_symbol(opaque, (), (relation,), {symbol.id: symbol}))
        self.assertIsNone(resolve_symbol(opaque, (), (), {}))


if __name__ == "__main__":
    unittest.main()
