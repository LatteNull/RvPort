"""合成事实验证已知执行依赖与用途闭包交集，不使用真实 parser。"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from kb_scanner.core import KnowledgeEntry, KnowledgeSnapshot, KnowledgeSource, NormalizedFact, stable_id
from kb_scanner.analyzers.candidate_usage.conflicts import ExecutionConflictIndex
from kb_scanner.detectors.matchers import KnowledgeIndex
from kb_scanner.analyzers.candidate_usage.proofs import materialize
from tests.unit.test_usage_proofs import proof_inputs


def inputs():
    facts, root, session, resolution, scopes = proof_inputs()
    source = KnowledgeSource(stable_id("source"), "unit", "generated", "facts.json", "0"*64)
    entry = KnowledgeEntry(stable_id("intrinsic"), "intrinsics", "x86", "_mm_setzero_ps", (source.id,))
    knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1", (source,), (entry,))
    evidence = replace(facts.evidence[1], id=stable_id("intrinsic-evidence"), kind="call_expression", value="_mm_setzero_ps")
    fact = NormalizedFact(stable_id("intrinsic-fact"), "symbol", root.subject_id, "_mm_setzero_ps", "local", (evidence.id,))
    return replace(facts, facts=(*facts.facts, fact), evidence=(*facts.evidence, evidence)), knowledge, root, session, resolution, scopes


class UsageConflictTests(unittest.TestCase):
    def test_unused_knowledge_is_not_indexed_but_full_index_decisions_are_preserved(self):
        facts, knowledge, root, session, resolution, scopes = inputs()
        unrelated = replace(knowledge.entries[0], id=stable_id('unused-header'), fact_kind='headers')
        knowledge = replace(knowledge, entries=(*knowledge.entries, unrelated))
        with patch('kb_scanner.analyzers.candidate_usage.conflicts.KnowledgeIndex', wraps=KnowledgeIndex) as build:
            narrowed = ExecutionConflictIndex(facts, knowledge, (root,))
        self.assertEqual({'intrinsics'}, {e.fact_kind for e in build.call_args.args[0].entries})
        with patch('kb_scanner.analyzers.candidate_usage.conflicts.KnowledgeIndex', return_value=KnowledgeIndex(knowledge)):
            full = ExecutionConflictIndex(facts, knowledge, (root,))
        self.assertEqual(full.locations, narrowed.locations)
        self.assertEqual(full.annotate(root, resolution, session, scopes),
                         narrowed.annotate(root, resolution, session, scopes))
        for snapshot in (replace(facts, facts=facts.facts[:-1]),
                         replace(facts, facts=(replace(facts.facts[-1], metadata={'configuration': 'other'}),))):
            with patch('kb_scanner.analyzers.candidate_usage.conflicts.KnowledgeIndex', side_effect=AssertionError('unused index')):
                empty = ExecutionConflictIndex(snapshot, knowledge, (root,))
            self.assertEqual({}, empty.locations)
            self.assertEqual((), empty.annotate(root, resolution, session, scopes)['conflictEvidenceIds'])

    def test_known_dependency_blocks_complete_data_proof_and_is_cached(self):
        facts, knowledge, root, session, resolution, scopes = inputs()
        index = ExecutionConflictIndex(facts, knowledge, (root,))
        result = index.annotate(root, resolution, session, scopes)
        self.assertEqual("unknown", result["status"])
        self.assertIn("usage-known-execution-conflict", result["reasonCodes"])
        self.assertEqual((facts.evidence[-1].id,), result["conflictEvidenceIds"])
        self.assertEqual(result, index.annotate(root, resolution, session, scopes))
        self.assertEqual(1, len(index.cache))
        _, _, proofs, summary = materialize(root, result, session, scopes)
        self.assertFalse(proofs)
        self.assertEqual(1, summary["conflictCount"])
        self.assertIn(facts.evidence[-1].id, summary["supportingEvidenceIds"])

    def test_unknown_other_scope_configuration_and_unrelated_spans_do_not_become_conflicts(self):
        facts, knowledge, root, session, resolution, scopes = inputs()
        fact, evidence = facts.facts[-1], facts.evidence[-1]
        for changed in (replace(fact, canonical_value="portable_decode"),
                        replace(fact, metadata={"configuration": "other"}),
                        replace(fact, context_ids=(stable_id("other"),)),
                        replace(fact, subject_id=stable_id("another-file")),
                        replace(fact, kind="compiler_argument", canonical_value="-march=rv64gc")):
            altered = replace(facts, facts=(*facts.facts[:-1], changed))
            index = ExecutionConflictIndex(altered, knowledge, (root,))
            self.assertEqual((), index.annotate(root, resolution, session, scopes)["conflictEvidenceIds"])
        span = evidence.location
        for changed in (replace(evidence, location=None),
                        replace(evidence, subject_id=stable_id("another-file")),
                        replace(evidence, location=replace(span, start=replace(span.start, column=None))),
                        replace(evidence, location=replace(span, end=replace(span.end, line=2, column=None))),
                        replace(evidence, location=replace(span, start=replace(span.start, line=5), end=replace(span.end, line=5))),
                        replace(evidence, location=replace(span, end=replace(span.end, line=5)))):
            altered = replace(facts, evidence=(*facts.evidence[:-1], changed))
            index = ExecutionConflictIndex(altered, knowledge, (root,))
            self.assertEqual((), index.annotate(root, resolution, session, scopes)["conflictEvidenceIds"])
        missing = replace(facts, evidence=facts.evidence[:-1])
        self.assertFalse(ExecutionConflictIndex(missing, knowledge, (root,)).locations)

    def test_conflicting_fact_order_and_duplicate_provenance_are_stable(self):
        facts, knowledge, root, session, resolution, scopes = inputs()
        first = ExecutionConflictIndex(facts, knowledge, (root,))
        duplicate = replace(facts.facts[-1], id=stable_id("duplicate-fact"))
        changed = replace(facts, facts=(duplicate, *reversed(facts.facts)))
        second = ExecutionConflictIndex(changed, knowledge, (root,))
        self.assertEqual(first.locations, second.locations)
        self.assertEqual(first.annotate(root, resolution, session, scopes), second.annotate(root, resolution, session, scopes))
        empty = {**resolution, "queries": ()}
        self.assertEqual((), first.annotate(root, empty, session, scopes)["conflictEvidenceIds"])
