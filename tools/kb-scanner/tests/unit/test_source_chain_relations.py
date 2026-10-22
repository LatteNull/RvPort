import unittest
from pathlib import Path

from kb_scanner.analyzers import GraphEntityIndexer, RelationBuilder
from tests.unit.evidence_graph.support import context, evidence, file, knowledge, snapshot


class NestedSourceGuardTests(unittest.TestCase):
    def test_missing_spans_and_invalid_relation_endpoints_fail_closed(self):
        from kb_scanner.analyzers.evidence_graph import _contains, _span_size, _validate_relations, _branch_role
        from kb_scanner.core import Relation, stable_id
        from types import SimpleNamespace
        self.assertFalse(_contains(None, None))
        self.assertEqual((10**9, 10**9), _span_size(None))
        self.assertEqual("unknown", _branch_role("riscv", knowledge(), fallback=False, negated=True)[0])
        self.assertEqual("generic", _branch_role("generic", knowledge(), fallback=False)[0])
        left, right = stable_id("left"), stable_id("right")
        relation = Relation(stable_id("rel"), "calls", left, right, ())
        with self.assertRaisesRegex(ValueError, "Entity"):
            _validate_relations(SimpleNamespace(entities={}), snapshot(), (relation,))
        relation = Relation(stable_id("rel2"), "calls", left, right, (stable_id("missing"),))
        with self.assertRaisesRegex(ValueError, "Evidence"):
            _validate_relations(SimpleNamespace(entities={left: None, right: None}), snapshot(), (relation,))

    def test_each_nested_guard_has_actual_parent_endpoint_and_no_sibling_join(self):
        source = file("x.cpp")
        outer = evidence(source, "preprocessor_condition", "defined(OUTER)", 1, end_line=20, metadata={"nodeType": "preproc_if"})
        inner = evidence(source, "preprocessor_condition", "defined(INNER)", 3, end_line=8, metadata={"nodeType": "preproc_if"})
        sibling = evidence(source, "preprocessor_condition", "defined(OTHER)", 10, end_line=14, metadata={"nodeType": "preproc_if"})
        call = evidence(source, "call_expression", "_mm_add_ps", 5)
        normalized = snapshot(source, evidence_items=(outer, inner, sibling, call))
        index = GraphEntityIndexer().index(context(Path("/project")), normalized, knowledge())
        relations, _ = RelationBuilder(context(Path("/project")), normalized, knowledge(), index).build()
        pairs = {(index.entities[r.source_id].properties.get("sourceEvidenceId"),
                  index.entities[r.target_id].properties.get("sourceEvidenceId"))
                 for r in relations if r.kind == "guarded_by"}
        self.assertIn((call.id, inner.id), pairs)
        self.assertIn((inner.id, outer.id), pairs)
        self.assertIn((sibling.id, outer.id), pairs)
        self.assertNotIn((inner.id, sibling.id), pairs)
