"""纯快照覆盖完整证明、残缺闭包和非执行图引用。"""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
from kb_scanner.core import Entity, stable_id

from kb_scanner.analyzers.candidate_usage.proofs import materialize, NON_EXECUTING
from kb_scanner.analyzers.candidate_usage.session import UsageSession, ScanBudget
from kb_scanner.analyzers.candidate_usage.closure import QueryBudget
from tests.unit.test_usage_session import inputs


def proof_inputs():
    facts, root = inputs()
    session = UsageSession(facts, (root,))
    resolution = session.resolve(root)
    scopes = {fact.id: fact for fact in facts.facts}
    return facts, root, session, resolution, scopes


class UsageProofTests(unittest.TestCase):
    def test_summary_is_immutable_and_shared_by_role_and_catalog(self):
        _, root, session, resolution, scopes = proof_inputs()
        _, relations, _, summary = materialize(root, resolution, session, scopes)
        role = next(item for item in relations if item.kind == 'has_semantic_role')
        catalog = Entity(stable_id('catalog'), 'candidate_usage_catalog', '审计', properties={'entries': (summary,)})
        self.assertIs(summary, role.metadata['usageProof'])
        self.assertIs(summary, catalog.properties['entries'][0])
        with self.assertRaises(TypeError):
            summary['budget']['visited'] = 0
        original_count = summary['budget']['visited']
        resolution['reasonCodes'] = ('changed',)
        self.assertEqual(original_count, summary['budget']['visited'])
        self.assertEqual('complete', summary['status'])

    def test_materialized_records_are_reused_but_configurations_are_isolated(self):
        _, root, session, resolution, scopes = proof_inputs()
        first = materialize(root, resolution, session, scopes)
        with patch('kb_scanner.analyzers.candidate_usage.proofs.stable_id', wraps=stable_id) as identity:
            second = materialize(root, resolution, session, scopes)
        self.assertEqual(first, second)
        self.assertFalse(any(call.args[0] in {'usage_record', 'usage_dependency', 'usage_scope_member', 'usage_scope_coverage'}
            for call in identity.call_args_list))
        old = {entity.id: entity for entity in first[0] if entity.kind == 'usage_record'}
        self.assertTrue(all(old[entity.id] is entity for entity in second[0] if entity.kind == 'usage_record'))
        configured = materialize(replace(root, configuration='other'), resolution, session, scopes)
        self.assertFalse(set(first[3]['recordIds']) & set(configured[3]['recordIds']))
        self.assertTrue(all(entity.properties['configuration'] == 'other'
            for entity in configured[0] if entity.kind == 'usage_record'))

    def test_shared_closure_materialization_preserves_distinct_root_and_budget(self):
        facts, root, session, resolution, scopes = proof_inputs()
        first = materialize(root, resolution, session, scopes)
        other = replace(root, fact_id=stable_id('another-fact'))
        cached = materialize(other, resolution, session, scopes)
        fresh_session = UsageSession(facts, (other,))
        fresh = materialize(other, fresh_session.resolve(other), fresh_session, scopes)
        self.assertEqual(cached, fresh)
        self.assertNotEqual(first[2][0].id, cached[2][0].id)
        self.assertEqual(1, len(session.materialized_queries))
        session.query_budget = QueryBudget(edges=1)
        limited = materialize(other, resolution, session, scopes)
        self.assertFalse(limited[2])
        self.assertIn('usage-proof-budget', limited[3]['reasonCodes'])
        sid, query = resolution['queries'][0]
        truncated = {**resolution, 'queries': ((sid, {**query, 'status': 'unknown', 'truncated': True}),)}
        self.assertIn('usage-query-incomplete', materialize(root, truncated, session, scopes)[3]['reasonCodes'])
        self.assertEqual(2, len(session.materialized_queries))

    def test_complete_graph_contains_auditable_scope_use_counts_and_sources(self):
        facts, root, session, resolution, scopes = proof_inputs()
        entities, relations, proofs, summary = materialize(root, resolution, session, scopes)
        self.assertEqual("complete", summary["status"])
        self.assertEqual(summary["expectedUseCount"], summary["resolvedUseCount"])
        self.assertGreater(summary["resolvedUseCount"], 0)
        self.assertEqual(4096, summary["budget"]["maxNodes"])
        self.assertEqual(len(summary["recordIds"]), summary["budget"]["visited"])
        ids = {entity.id for entity in entities} | {root.subject_id}
        for relation in relations:
            self.assertIn(relation.source_id, ids)
            self.assertIn(relation.target_id, ids)
            self.assertEqual(NON_EXECUTING, relation.metadata["semanticRole"])
            self.assertTrue(set(relation.evidence_ids).issubset(item.id for item in facts.evidence))
            self.assertNotIn(relation.kind, {"selects", "alternative_to", "guarded_by"})
        self.assertEqual(1, len(proofs))
        self.assertEqual(root.subject_id, proofs[0].source_id)
        self.assertTrue(all(item.location for item in entities if item.kind == "usage_record"))
        self.assertEqual((entities, relations, proofs, summary), materialize(root, resolution, session, scopes))

    def test_incomplete_roots_queries_and_budget_never_generate_role(self):
        facts, root, session, resolution, scopes = proof_inputs()
        for broken in ({**resolution, "bindings": ()},
                       {**resolution, "reasonCodes": ("usage-unknown-call",)},
                       {**resolution, "queries": ()}):
            entities, relations, proofs, summary = materialize(root, broken, session, scopes)
            self.assertFalse(proofs)
            self.assertEqual("unknown", summary["status"])
            self.assertFalse(any(r.kind == "has_semantic_role" for r in relations))
        limited = UsageSession(facts, (root,), ScanBudget(visits=1))
        result = materialize(root, limited.resolve(root), limited, scopes)
        self.assertFalse(result[2])
        self.assertTrue(result[3]["truncated"])

    def test_all_uses_and_link_endpoints_are_verified_not_only_complete_flag(self):
        _, root, session, resolution, scopes = proof_inputs()
        sid, query = resolution["queries"][0]
        declaration = next(key for key in query["useKeys"] if session.indexes[sid].rows[key]["binding"]["role"] == "declaration")
        removed = {**query, "recordKeys": tuple(key for key in query["recordKeys"] if key != declaration)}
        result = materialize(root, {**resolution, "queries": ((sid, removed),)}, session, scopes)
        self.assertFalse(result[2])
        self.assertIn("usage-uses-not-closed", result[3]["reasonCodes"])
        self.assertIn("usage-links-not-closed", result[3]["reasonCodes"])
        eid, _, _ = resolution["bindings"][0]
        missing = {**resolution, "bindings": ((eid, sid, (100, 101, "identifier")),)}
        self.assertIn("usage-root-record-missing", materialize(root, missing, session, scopes)[3]["reasonCodes"])

    def test_membership_edges_and_scan_budget_are_part_of_proof_limits(self):
        facts, root, session, resolution, scopes = proof_inputs()
        session.query_budget = QueryBudget(edges=1)
        _, _, proofs, summary = materialize(root, resolution, session, scopes)
        self.assertFalse(proofs)
        self.assertTrue(summary["truncated"])
        self.assertIn("usage-proof-budget", summary["reasonCodes"])
        session.query_budget = QueryBudget()
        changed = {**resolution, "reasonCodes": ("usage-scan-record-budget",), "queries": (), "bindings": ()}
        _, _, proofs, summary = materialize(root, changed, session, scopes)
        self.assertFalse(proofs)
        self.assertTrue(summary["truncated"])
        self.assertEqual(0, summary["budget"]["visited"])
