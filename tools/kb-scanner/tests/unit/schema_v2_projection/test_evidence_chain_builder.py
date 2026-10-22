from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from pathlib import Path

from kb_scanner.core import Classification, stable_id
from kb_scanner.projection.v2.chain import EvidenceChainBuilder, _completion, _reason_codes, _value
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.index import SnapshotIndex
from kb_scanner.projection.v2.source_chain import Arc, Query
from .support import graph_with_source


class EvidenceChainTests(unittest.TestCase):
    def test_shared_steps_edges_and_incoming_metadata_do_not_leak_between_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            values, index, builder = self._parts(Path(temp))
            original = values[7].classifications[0]
            anchor = next(iter(index.evidence.values()))
            left = replace(anchor, id=stable_id('left'), value='selector')
            other = replace(anchor, id=stable_id('other'), value='other selector')
            index = replace(index, evidence={**index.evidence, left.id: left, other.id: other})
            builder = EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(temp)))
            rid = next(iter(index.relations))
            arc = Arc(left.id, anchor.id, 'selects', (rid,))
            alternate = Arc(other.id, anchor.id, 'selects', (rid,))
            def build(arcs):
                query = Query((anchor.id, left.id, other.id), arcs, (), 3, 1)
                with patch.object(builder._source_index, 'query', return_value=query):
                    return builder.build(original, anchor_id=anchor.id)
            first = build((arc,))
            snapshot = first.model_dump()
            repeated = build((arc,))
            expanded = build((arc, alternate))
            base = builder._evidence_step(anchor)
            key = 'org.rvport.kb-scanner.source-chain'
            self.assertNotIn(key, base.extensions or {})
            target = lambda chain: next(s for s in chain.steps if s.id == base.id)
            self.assertIs(target(first), target(repeated))
            self.assertEqual(1, len(target(first).extensions[key]['incoming']))
            self.assertEqual(2, len(target(expanded).extensions[key]['incoming']))
            self.assertEqual(snapshot, first.model_dump())
            self.assertEqual(snapshot, build((arc,)).model_dump())
            self.assertIs(next(e for e in first.edges if e.kind == 'selects'),
                          next(e for e in repeated.edges if e.kind == 'selects'))

    def _parts(self, root):
        values = graph_with_source(root)
        context, _, knowledge, frontend, facts, analysis, detections, classifications, assessments, _ = values
        index = SnapshotIndex.build(knowledge, frontend, facts, analysis, detections, classifications, assessments)
        return values, index, EvidenceChainBuilder(index, knowledge, SourceContextProjector(context.input_root))

    def test_local_hit_keeps_knowledge_side_branch_and_no_analysis_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            values, index, builder = self._parts(Path(temp))
            chain = builder.build(values[7].classifications[0])
            self.assertEqual("partial", chain.status)
            self.assertEqual({"intrinsic_call", "knowledge_match"}, {item.kind for item in chain.steps})
            self.assertEqual(1, len(chain.primaryPath))
            self.assertEqual(["matches_knowledge"], [edge.kind for edge in chain.edges])
            self.assertEqual((), chain.impactStepIds)
            self.assertIs(index.evidence, index.evidence)

    def test_missing_reference_and_budget_make_explicit_breaks(self):
        with tempfile.TemporaryDirectory() as temp:
            values, index, _ = self._parts(Path(temp))
            original = values[7].classifications[0]
            broken = Classification(
                original.id, original.policy_id, original.impact, original.reason, original.observation_ids,
                (*original.evidence_ids, stable_id("missing")), original.knowledge_ids,
                original.relation_ids, original.proof_path_ids, original.confidence, original.metadata,
            )
            builder = EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(temp)), max_depth=2, max_visited=2)
            chain = builder.build(broken)
            self.assertEqual("partial", chain.status)
            self.assertIn("missing_reference", chain.reasonCodes)
            self.assertTrue(chain.breaks)

    def test_conflicting_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            values = graph_with_source(Path(temp))
            evidence = values[3].evidence[0]
            from kb_scanner.core import FrontendSnapshot, Evidence
            other = Evidence(evidence.id, evidence.kind, evidence.subject_id, "different", evidence.producer, evidence.parse_mode, evidence.confidence, evidence.location)
            with self.assertRaises(ValueError):
                SnapshotIndex.build(values[2], FrontendSnapshot(values[3].entities, (evidence, other)), values[4], values[5], values[6], values[7], values[8])

    def test_semantic_helpers_cover_selector_macro_and_status_vocabulary(self):
        self.assertIn("a", _value({"a": 1}))
        with tempfile.TemporaryDirectory() as temp:
            values, _, builder = self._parts(Path(temp))
            original = values[7].classifications[0]
            inactive = Classification(original.id, original.policy_id, "guarded_inactive", original.reason, original.observation_ids, original.evidence_ids, original.knowledge_ids, original.relation_ids, original.proof_path_ids, original.confidence)
            self.assertEqual("inactive", _completion(inactive))
            self.assertEqual(("inactive_branch",), _reason_codes(inactive))
            partial = Classification(original.id, original.policy_id, original.impact, original.reason, original.observation_ids, original.evidence_ids, original.knowledge_ids, original.relation_ids, original.proof_path_ids, original.confidence, {"completeness": "partial"})
            self.assertEqual("partial", _completion(partial))
            chain = builder.build(inactive)
            self.assertEqual("partial", chain.status)
            self.assertTrue(chain.breaks)
