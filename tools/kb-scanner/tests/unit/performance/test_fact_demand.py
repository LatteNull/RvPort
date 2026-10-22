from dataclasses import replace
import unittest

from kb_scanner.core import NormalizedFact, NormalizedSnapshot, stable_id
from kb_scanner.detectors.demand import FactProofDemand
from tests.unit.knowledge_detection.test_local_detector import inputs


class FactDemandTests(unittest.TestCase):
    def test_analyzer_keeps_facts_base_graph_and_all_demand_related_proofs(self):
        from pathlib import Path
        from kb_scanner.analyzers import EvidenceGraphAnalyzer
        from kb_scanner.core import FrontendSnapshot, KnowledgeEntry, KnowledgeSnapshot
        from kb_scanner.normalization import CppEvidenceNormalizer
        from tests.unit.evidence_graph.test_evidence_graph_analyzer import macro_fixture
        from tests.unit.evidence_graph.support import context, evidence
        snapshot, _ = macro_fixture()
        definition = evidence(snapshot.entities[1], "macro_definition", "ORDINARY", 20)
        replacement = evidence(snapshot.entities[1], "macro_replacement_token", "ordinary_helper", 20,
                               metadata={"macroDefinitionEvidenceId": definition.id, "tokenRole": "call_candidate"})
        ctx = context(Path("/virtual"))
        facts = CppEvidenceNormalizer().normalize(ctx, FrontendSnapshot(snapshot.entities, (*snapshot.evidence, definition, replacement))).value
        entry = KnowledgeEntry(stable_id("intrinsic"), "intrinsics", "x86", "_mm_add_ps", (stable_id("knowledge-source"),))
        kb = KnowledgeSnapshot(stable_id("kb"), "1", entries=(entry,))
        original = EvidenceGraphAnalyzer().analyze(ctx, facts, kb)
        selected = EvidenceGraphAnalyzer(demand_selector=FactProofDemand()).analyze(ctx, facts, kb)
        self.assertEqual(original.value.entities, selected.value.entities)
        base = lambda value: tuple(r for r in value.relations if r.kind != "reachable_from")
        self.assertEqual(base(original.value), base(selected.value))
        requests = FactProofDemand()(facts, kb)
        by_id = {r.id: r for r in original.value.relations}
        expected = tuple(p for p in original.value.proof_paths if any(e in requests for r in p.relation_ids for e in by_id[r].evidence_ids))
        self.assertTrue(expected)
        self.assertLess(len(expected), len(original.value.proof_paths))
        self.assertEqual(expected, selected.value.proof_paths)
        self.assertEqual(original.diagnostics, selected.diagnostics)
        empty = EvidenceGraphAnalyzer(demand_selector=FactProofDemand()).analyze(ctx, facts, replace(kb, entries=()))
        self.assertEqual((), empty.value.proof_paths)
        self.assertEqual(base(original.value), base(empty.value))

    def test_reuses_rules_for_confirmed_candidate_hint_and_unknown_asm(self):
        facts, knowledge = inputs()
        records = [("macro", "MY_AVX"), ("comment", "x86 implementation"),
                   ("inline_asm", "unrecognized opcode"), ("enum_reference", "Backend::avx2"),
                   ("symbol", "ordinary_helper"), ("unrelated", "x86")]
        added = tuple(NormalizedFact(stable_id("fact", i), kind, facts.entities[0].id, value,
                                    "scope", (stable_id("evidence", i),),
                                    context_ids=(stable_id("context", i),), producers=("test",))
                      for i, (kind, value) in enumerate(records))
        selector = FactProofDemand()
        enriched = replace(facts, facts=(*facts.facts, *added))
        expected = frozenset((*facts.facts[0].evidence_ids, *(e for f in added[:4] for e in f.evidence_ids)))
        self.assertEqual(expected, selector(enriched, knowledge))
        self.assertEqual(expected, selector(replace(enriched, facts=tuple(reversed(enriched.facts))), knowledge))
        self.assertEqual(frozenset(), selector(NormalizedSnapshot(), knowledge))
        self.assertEqual(frozenset(), FactProofDemand({})(enriched, knowledge))

    def test_matcher_injection_preserves_all_producer_evidence_without_mutation(self):
        facts, knowledge = inputs()
        original = facts
        evidence_ids = (*facts.facts[0].evidence_ids, stable_id("second-producer"))
        facts = replace(facts, facts=(replace(facts.facts[0], evidence_ids=evidence_ids),))
        visits = []
        def matcher(definition, fact, index):
            visits.append((definition.input_kind, fact.id))
            return object()
        self.assertEqual(frozenset(evidence_ids), FactProofDemand(matcher=matcher)(facts, knowledge))
        self.assertEqual(1, len(visits))
        self.assertEqual(1, len(original.facts[0].evidence_ids))
