import unittest
from dataclasses import replace
from pathlib import Path

from kb_scanner.core import Entity, Relation, stable_id
from kb_scanner.projection.v2.chain import EvidenceChainBuilder, _relation_completion
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.index import SnapshotIndex
from tests.unit.compatible_cutover.support import graph


class SourceEvidenceChainTests(unittest.TestCase):
    def parts(self, status="complete", configs=("default",)):
        values = graph(Path("/project"))
        index = SnapshotIndex.build(*values[2:9])
        hit = values[3].evidence[0]
        other = replace(hit, id=stable_id("other"), kind="macro_definition", value="WRAP")
        source = Entity(stable_id("source"), "macro_definition", "WRAP", properties={"sourceEvidenceId": other.id})
        target = Entity(stable_id("target"), "call_site", "call", properties={"sourceEvidenceId": hit.id})
        relations = tuple(Relation(stable_id("link", config), "expands_to", source.id, target.id, (other.id, hit.id),
                                   "high", status, {"configuration": config}) for config in configs)
        index = replace(index, evidence={hit.id: hit, other.id: other}, entities={source.id: source, target.id: target},
                        relations={**index.relations, **{r.id: r for r in relations}})
        return values, index, hit, other

    def builder(self, values, index, **limits):
        return EvidenceChainBuilder(index, values[2], SourceContextProjector(Path("/project"), reader=lambda _: "abcdefghij\n" * 30), **limits)

    def test_connected_primary_path_contains_hit_and_real_relation_provenance(self):
        values, index, hit, other = self.parts()
        chain = self.builder(values, index).build(values[7].classifications[0], anchor_id=hit.id)
        steps = {s.id: s for s in chain.steps}
        self.assertEqual([other.id, hit.id], [steps[sid].provenance[0].id for sid in chain.primaryPath])
        self.assertEqual("complete", chain.status)
        self.assertEqual((), chain.impactStepIds)
        self.assertTrue(all(steps[sid].kind != "knowledge_match" for sid in chain.primaryPath))
        actual = next(e for e in chain.edges if e.kind == "expands_to")
        self.assertEqual("expands_to", index.relations[actual.provenance[0].id].kind)
        self.assertTrue(steps[actual.toStepId].extensions["org.rvport.kb-scanner.source-chain"]["incoming"])

    def test_unknown_ambiguous_and_conflicting_configuration_never_become_complete(self):
        for state, configs, expected in (("unknown", ("default",), "partial"), ("partial", ("default",), "partial"),
                                        ("ambiguous", ("default",), "ambiguous"), ("complete", ("a", "b"), "ambiguous")):
            values, index, hit, _ = self.parts(state, configs)
            chain = self.builder(values, index).build(values[7].classifications[0], anchor_id=hit.id)
            self.assertEqual(expected, chain.status)
            self.assertTrue(chain.breaks)
            self.assertTrue(all(b.stage != "classification" for b in chain.breaks))
        self.assertEqual("unknown", _relation_completion("unexpected"))

    def test_missing_observation_proof_and_overflow_are_explicit(self):
        values, index, hit, other = self.parts()
        classification = replace(values[7].classifications[0], observation_ids=(stable_id("missing-observation"),),
                                 proof_path_ids=(stable_id("missing-proof"),), evidence_ids=(other.id, hit.id))
        chain = self.builder(values, index, max_visited=1).build(classification, anchor_id=hit.id)
        self.assertIn("missing_reference", chain.reasonCodes)
        self.assertIn("reference_budget_exceeded", chain.reasonCodes)
        self.assertEqual(1, len(chain.steps))
        self.assertEqual(hit.id, chain.steps[0].provenance[0].id)
        with self.assertRaises(ValueError):
            self.builder(values, replace(index, evidence={})).build(classification)

    def test_classification_completeness_and_knowledge_applicability_are_independent(self):
        values, index, hit, _ = self.parts()
        for state in ("partial", "unknown", "ambiguous"):
            classification = replace(values[7].classifications[0], metadata={"completeness": state})
            chain = self.builder(values, index).build(classification, anchor_id=hit.id)
            self.assertEqual(state, chain.status)
            self.assertTrue(chain.breaks)
        different_kind = replace(hit, kind="comment")
        chain = self.builder(values, replace(index, evidence={**index.evidence, hit.id: different_kind})).build(values[7].classifications[0], anchor_id=hit.id)
        self.assertFalse(any(e.kind == "matches_knowledge" for e in chain.edges))

    def test_multiple_occurrences_missing_locations_and_shared_budget(self):
        values, index, hit, other = self.parts()
        unlocated = replace(hit, id=stable_id("unlocated"), location=None)
        index = replace(index, evidence={**index.evidence, unlocated.id: unlocated})
        classification = values[7].classifications[0]
        chain = self.builder(values, index).build(classification, anchor_id=hit.id,
            occurrence_ids=(other.id, unlocated.id, stable_id("absent")))
        self.assertIn("missing_reference", chain.reasonCodes)
        self.assertEqual({other.id, hit.id}, {s.provenance[0].id for s in chain.steps if s.source})
        self.assertGreater(chain.budget.visited, 2)
        limited = self.builder(values, index, max_visited=1).build(classification, anchor_id=hit.id, occurrence_ids=(other.id,))
        self.assertTrue(limited.budget.truncated)
        self.assertIn("reference_budget_exceeded", limited.reasonCodes)

    def test_unbound_condition_is_a_source_gap_even_with_local_edges(self):
        values, index, hit, other = self.parts()
        guard = replace(other, kind="preprocessor_condition", value="defined(FLAG)")
        chain = self.builder(values, replace(index, evidence={hit.id: hit, other.id: guard})).build(values[7].classifications[0], anchor_id=hit.id)
        self.assertIn("missing_input", chain.reasonCodes)
        self.assertEqual("partial", chain.status)

    def test_one_occurrence_cannot_supply_another_occurrences_missing_upstream(self):
        values, index, hit, _ = self.parts()
        isolated = replace(hit, id=stable_id("isolated-hit"))
        index = replace(index, evidence={**index.evidence, isolated.id: isolated})
        for anchor, occurrences in ((hit.id, (isolated.id,)), (isolated.id, (hit.id,))):
            chain = self.builder(values, index).build(values[7].classifications[0], anchor_id=anchor, occurrence_ids=occurrences)
            self.assertIn("missing_input", chain.reasonCodes)
            self.assertEqual("partial", chain.status)
