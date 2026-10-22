"""需求选择与 Detector 一致性，使用纯事实和内存知识。"""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from kb_scanner.analyzers.candidate_usage.demand import CandidateUsageDemand
from kb_scanner.core import AnalysisSnapshot, KnowledgeEntry, KnowledgeSnapshot, NormalizedSnapshot, NormalizedFact, stable_id
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.detectors.definitions import DEFAULT_DEFINITIONS, DetectorDefinition
from kb_scanner.detectors.matchers import MatchResult, KnowledgeIndex
from tests.unit.knowledge_detection.support import make_entity, make_evidence, make_context


def inputs():
    entity = make_entity()
    evidence = make_evidence(entity, "macro_definition", "FORMAT_X86")
    fact = NormalizedFact(stable_id("usage-fact"), "macro", entity.id, "FORMAT_X86", "local", (evidence.id,))
    return NormalizedSnapshot((entity,), (evidence,), (fact,)), KnowledgeSnapshot(stable_id("usage-knowledge"), "1")


class UsageDemandTests(unittest.TestCase):
    def test_prepared_index_is_demanded_by_definitions_and_equals_full_knowledge(self):
        facts, empty = inputs()
        kinds = ('intrinsics', 'platformMacros', 'architectureAliases', 'targetFeatures', 'headers')
        knowledge = replace(empty, entries=tuple(KnowledgeEntry(stable_id('entry', kind), kind, 'x86',
            'FORMAT_X86', (stable_id('source'),)) for kind in kinds))
        for definitions, expected in ((DEFAULT_DEFINITIONS, {'platformMacros', 'architectureAliases', 'targetFeatures'}),
                ({'candidate': DEFAULT_DEFINITIONS['C_CPP.X86.ARCH_MACRO_CANDIDATE'],
                  'known': DetectorDefinition('macro-known', 'macro', ('intrinsics',), 'x86_intrinsic_reference', 'exact')},
                 {'intrinsics'})):
            selector = CandidateUsageDemand(definitions)
            prepared = selector.prepare(knowledge)
            self.assertEqual(expected, set(prepared[0].by_kind))
            self.assertEqual(expected, {entry.fact_kind for entry in prepared[1].values()})
            full = KnowledgeIndex(knowledge), {entry.id: entry for entry in knowledge.entries}
            self.assertEqual(selector.select(facts, knowledge, prepared=full),
                             selector.select(facts, knowledge, prepared=prepared))
        self.assertEqual(set(kinds), {entry.fact_kind for entry in knowledge.entries})

    def test_repeated_values_reuse_matching_not_fact_or_configuration_identity(self):
        from kb_scanner.detectors.matchers import match_fact
        facts, knowledge = inputs()
        first = facts.facts[0]
        second = replace(first, id=stable_id('second'), metadata={'configuration': 'separate'})
        facts = replace(facts, facts=(first, second))
        selector = CandidateUsageDemand()
        with patch('kb_scanner.analyzers.candidate_usage.demand.match_fact', wraps=match_fact) as matcher:
            roots = selector.select(facts, knowledge)
        self.assertEqual({first.id, second.id}, {root.fact_id for root in roots})
        self.assertEqual({'default', 'separate'}, {root.configuration for root in roots})
        self.assertEqual(sum(item.input_kind == first.kind for item in selector.definitions), matcher.call_count)

    def test_no_candidate_and_unrelated_fact_fast_path(self):
        facts, knowledge = inputs()
        demand = CandidateUsageDemand()
        for kind, value in (("usage_scope", "local-use-scope"), ("macro", "ordinary")):
            modified = replace(facts, facts=(replace(facts.facts[0], kind=kind, canonical_value=value),))
            self.assertEqual((), demand.select(modified, knowledge))
        self.assertEqual((), demand.select(NormalizedSnapshot(), knowledge))

    def test_exact_root_metadata_and_input_order_match_detector(self):
        facts, knowledge = inputs()
        fact = facts.facts[0]
        second = replace(facts.evidence[0], id=stable_id("second-root"), producer="clang")
        fact = replace(fact, evidence_ids=(second.id, *fact.evidence_ids))
        facts = replace(facts, evidence=(*facts.evidence, second), facts=(fact,))
        for configuration in ("default", "source-unconfigured", stable_id("configuration")):
            scoped = replace(facts, facts=(replace(fact, metadata={"configuration": configuration}),))
            selected = CandidateUsageDemand().select(scoped, knowledge)
            observed = LocalX86Detector(deferred_capabilities={}).detect(
                make_context(Path("/tmp")), scoped, AnalysisSnapshot(), knowledge).value.observations[0]
            self.assertEqual(1, len(selected))
            self.assertEqual(observed.metadata["factId"], selected[0].fact_id)
            self.assertEqual(observed.metadata["subjectId"], selected[0].subject_id)
            self.assertEqual(observed.metadata["configuration"], selected[0].configuration)
            self.assertEqual(observed.metadata["matchedEvidenceIds"], selected[0].matched_evidence_ids)
            self.assertTrue(selected[0].configuration_complete)
            self.assertEqual(selected, CandidateUsageDemand().select(replace(scoped, facts=tuple(reversed(scoped.facts))), knowledge))

    def test_referenced_enum_declaration_is_not_a_second_demand(self):
        facts, knowledge = inputs()
        member = replace(facts.facts[0], kind="enum_member", canonical_value="Format::X86")
        ref = replace(member, id=stable_id("ref"), kind="enum_reference", evidence_ids=(stable_id("ref-evidence"),),
            metadata={"enumMemberDeclarationEvidenceIds": member.evidence_ids})
        self.assertEqual((ref.id,), tuple(root.fact_id for root in CandidateUsageDemand().select(
            replace(facts, facts=(member, ref)), knowledge)))
        self.assertEqual((member.id,), tuple(root.fact_id for root in CandidateUsageDemand().select(
            replace(facts, facts=(member,)), knowledge)))

    def test_multiple_and_invalid_configurations_cannot_claim_completion(self):
        facts, knowledge = inputs()
        cfg = stable_id("cfg")
        for contexts, metadata, expected in (
            ((cfg,), {"compilationContextId": cfg}, True),
            ((cfg,), {}, False),
            ((cfg, stable_id("cfg2")), {"compilationContextId": cfg}, False),
            ((), {"configuration": None}, False),
            ((), {"configuration": ""}, False),
        ):
            fact = replace(facts.facts[0], context_ids=contexts, metadata=metadata)
            root = CandidateUsageDemand().select(replace(facts, facts=(fact,)), knowledge)[0]
            self.assertEqual(expected, root.configuration_complete)

    def test_confirmed_coverage_reuses_existing_helper(self):
        facts, knowledge = inputs()
        with patch("kb_scanner.analyzers.candidate_usage.demand.covered_identifier_candidate", return_value=True) as coverage:
            self.assertEqual((), CandidateUsageDemand().select(facts, knowledge))
            self.assertTrue(coverage.called)
        definition = DEFAULT_DEFINITIONS["C_CPP.X86.ARCH_MACRO_CANDIDATE"]
        with patch("kb_scanner.analyzers.candidate_usage.demand.match_fact", return_value=MatchResult((), "confirmed_local", "fake")):
            self.assertEqual((), CandidateUsageDemand({"test": definition}).select(facts, knowledge))
