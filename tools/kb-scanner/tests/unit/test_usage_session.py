"""纯快照验证配置隔离、精确根、多 occurrence、缓存及扫描级预算。"""
from dataclasses import replace
import unittest

from kb_scanner.core import Entity, Evidence, NormalizedFact, NormalizedSnapshot, SourceSpan, SourceLocation, stable_id
from kb_scanner.analyzers.candidate_usage.demand import UsageRoot
from kb_scanner.analyzers.candidate_usage.session import UsageSession, ScanBudget
from tests.unit.test_usage_closure import scope, base


def inputs():
    rows = base()
    file_id = stable_id("usage-file")
    entity = Entity(file_id, "source_file", "a.c")
    span = SourceSpan(SourceLocation("a.c", 1, 1), SourceLocation("a.c", 1, 100))
    scope_evidence = Evidence(stable_id("usage-scope"), "usage_scope", file_id,
        "local-use-scope", "fake", "fake", "medium", span)
    structure = {**scope(rows), "recordCount": len(rows)}
    fact = NormalizedFact(stable_id("usage-normalized"), "usage_scope", file_id,
        "local-use-scope", "scope", (scope_evidence.id,), metadata={"usageScope": structure})
    anchor = Evidence(stable_id("root"), "enum_member_reference", file_id, "X86", "fake", "fake", "medium",
        SourceSpan(SourceLocation("a.c", 1, 5), SourceLocation("a.c", 1, 6)))
    root = UsageRoot(stable_id("candidate"), file_id, "default", (anchor.id,), True)
    return NormalizedSnapshot((entity,), (scope_evidence, anchor), (fact,)), root


class UsageSessionTests(unittest.TestCase):
    def test_exhausted_collection_budget_retains_facts_without_attempting_proof_query(self):
        from unittest.mock import patch
        from kb_scanner.analyzers.candidate_usage.proofs import materialize
        facts, root = inputs()
        scoped = facts.facts[0]
        for reason in ('usage-file-budget', 'usage-scope-budget', 'usage-scan-record-budget'):
            limited = replace(scoped, metadata={'usageScope': {**scoped.metadata['usageScope'],
                'status': 'partial', 'reasonCodes': (reason,)}})
            snapshot = replace(facts, facts=(limited,))
            session = UsageSession(snapshot, (root,))
            with patch('kb_scanner.analyzers.candidate_usage.session.query', side_effect=AssertionError('no budget query')):
                result = session.resolve(root)
            self.assertEqual('unknown', result['status'])
            self.assertIn(reason, result['reasonCodes'])
            self.assertEqual((), result['queries'])
            self.assertEqual(0, session.visits)
            self.assertFalse(session.indexes)
            self.assertEqual(scoped.metadata['usageScope']['records'], limited.metadata['usageScope']['records'])
            self.assertEqual(facts.evidence, snapshot.evidence)
            produced = materialize(root, result, session, {limited.id: limited})
            self.assertFalse(produced[2])
            self.assertTrue(produced[3]['truncated'])
            self.assertEqual(root.matched_evidence_ids, produced[3]['matchedEvidenceIds'])
        # 非预算不完整性继续查询实际断点，不能统统短路成“预算未知”。
        partial = replace(scoped, metadata={'usageScope': {**scoped.metadata['usageScope'],
            'status': 'partial', 'reasonCodes': ('usage-partial-parse',)}})
        result = UsageSession(replace(facts, facts=(partial,)), (root,)).resolve(root)
        self.assertTrue(result['queries'])
        self.assertIn('usage-partial-parse', result['reasonCodes'])

    def test_empty_truncated_inventory_keeps_budget_reason_even_without_root_binding(self):
        facts, root = inputs()
        scoped = facts.facts[0]
        cropped = replace(scoped, metadata={"usageScope": {**scoped.metadata['usageScope'],
            'records': (), 'recordCount': 0, 'status': 'partial', 'reasonCodes': ('usage-scan-record-budget',)}})
        facts = replace(facts, facts=(cropped,))
        session = UsageSession(facts, (root,))
        result = session.resolve(root)
        self.assertEqual('unknown', result['status'])
        self.assertIn('usage-scan-record-budget', result['reasonCodes'])
        self.assertIn('usage-scope-incomplete', result['reasonCodes'])
        from kb_scanner.analyzers.candidate_usage.proofs import materialize
        self.assertTrue(materialize(root, result, session, {cropped.id: cropped})[3]['truncated'])

    def test_closed_uses_cache_and_no_demand_fast_path(self):
        facts, root = inputs()
        session = UsageSession(facts, (root,))
        result = session.resolve(root)
        self.assertEqual("complete", result["status"])
        self.assertEqual(1, len(result["bindings"]))
        self.assertEqual(result, session.resolve(root))
        self.assertEqual(1, session.cache_hits)
        self.assertEqual(1, len(session.indexes))
        self.assertGreater(session.visits, 0)
        self.assertFalse(UsageSession(facts, ()).scopes)

    def test_exact_occurrence_and_configuration_are_required(self):
        facts, root = inputs()
        for changed, reason in ((replace(root, configuration="other"), "usage-open-scope"),
                                (replace(root, configuration_complete=False), "usage-configuration-unknown"),
                                (replace(root, matched_evidence_ids=(stable_id("missing"),)), "usage-root-unresolved")):
            result = UsageSession(facts, (changed,)).resolve(changed)
            self.assertEqual("unknown", result["status"])
            self.assertIn(reason, result["reasonCodes"])
        for updates, reason in (({"value": "another"}, "usage-root-binding-unknown"),
                                ({"location": None}, "usage-root-unresolved"),
                                ({"kind": "macro_definition"}, "usage-root-unresolved")):
            altered = replace(facts, evidence=(facts.evidence[0], replace(facts.evidence[1], **updates)))
            self.assertIn(reason, UsageSession(altered, (root,)).resolve(root)["reasonCodes"])

    def test_open_range_and_all_occurrences(self):
        facts, root = inputs()
        for span, reason in ((SourceSpan(SourceLocation("a.c", 1, 5), SourceLocation("a.c", 2, 1)), "usage-root-range-unknown"),
                             (SourceSpan(SourceLocation("a.c", 2, 1), SourceLocation("a.c", 2, 2)), "usage-open-scope")):
            altered = replace(facts, evidence=(facts.evidence[0], replace(facts.evidence[1], location=span)))
            self.assertIn(reason, UsageSession(altered, (root,)).resolve(root)["reasonCodes"])
        aggregate = replace(root, matched_evidence_ids=(*root.matched_evidence_ids, stable_id("missing")))
        result = UsageSession(facts, (aggregate,)).resolve(aggregate)
        self.assertEqual("unknown", result["status"])
        self.assertIn("usage-roots-incomplete", result["reasonCodes"])
        self.assertTrue(result["queries"])

    def test_record_and_visit_budgets_do_not_claim_completeness(self):
        facts, root = inputs()
        for budget, reason in ((ScanBudget(records=0), "usage-scan-record-budget"),
                               (ScanBudget(visits=0), "usage-scan-visit-budget")):
            result = UsageSession(facts, (root,), budget).resolve(root)
            self.assertEqual("unknown", result["status"])
            self.assertIn(reason, result["reasonCodes"])
        for bad in (-1, True, "0"):
            with self.assertRaises(ValueError):
                ScanBudget(records=bad)
        for options in ({"records": 100001}, {"visits": 1000001}):
            with self.assertRaises(ValueError):
                ScanBudget(**options)

    def test_invalid_or_ambiguous_scope_records_remain_unknown(self):
        facts, root = inputs()
        for altered in (replace(facts, evidence=facts.evidence[1:]),
                        replace(facts, evidence=(replace(facts.evidence[0], location=None), facts.evidence[1])),
                        replace(facts, evidence=(replace(facts.evidence[0], subject_id=stable_id("another")), facts.evidence[1]))):
            self.assertIn("usage-open-scope", UsageSession(altered, (root,)).resolve(root)["reasonCodes"])
        missing = replace(facts, facts=(replace(facts.facts[0], metadata={}),))
        self.assertIn("usage-scope-unavailable", UsageSession(missing, (root,)).resolve(root)["reasonCodes"])
        duplicate = replace(facts, facts=(*facts.facts, replace(facts.facts[0], id=stable_id("another-scope"))))
        self.assertIn("usage-scope-ambiguous", UsageSession(duplicate, (root,)).resolve(root)["reasonCodes"])

    def test_declared_definition_must_cover_later_escape_and_all_roots_share_budget(self):
        facts, root = inputs()
        declaration = replace(facts.evidence[1], id=stable_id("declaration-root"), kind="enum_member_declaration",
            location=SourceSpan(SourceLocation("a.c", 1, 4), SourceLocation("a.c", 1, 5)))
        expanded = replace(facts, evidence=(*facts.evidence, declaration))
        defined = replace(root, matched_evidence_ids=(declaration.id,))
        session = UsageSession(expanded, (root, defined))
        use = session.resolve(root)
        definition = session.resolve(defined)
        self.assertEqual(use["queries"][0][1]["useKeys"], definition["queries"][0][1]["useKeys"])
        self.assertEqual("complete", definition["status"])
        self.assertEqual(1, len(session.indexes))
        from kb_scanner.analyzers.candidate_usage.closure import QueryBudget
        limited = UsageSession(expanded, (root, defined), ScanBudget(visits=1), QueryBudget(nodes=1))
        limited.resolve(root)
        self.assertEqual(1, limited.visits)
        second = limited.resolve(defined)
        self.assertIn("usage-scan-visit-budget", second["reasonCodes"])
        self.assertEqual(1, limited.visits)
