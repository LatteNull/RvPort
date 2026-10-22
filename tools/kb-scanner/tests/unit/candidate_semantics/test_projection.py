from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as S
import tempfile
import unittest

from kb_scanner.core import Entity, Relation, stable_id
from kb_scanner.projection.v2.chain import EvidenceChainBuilder, _relation_completion
from kb_scanner.projection.v2.source_chain import SourceChainIndex
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.evidence_kinds import intrinsic_symbols, is_intrinsic
from kb_scanner.projection.v2.index import SnapshotIndex
from kb_scanner.projection.v2.mapper import V2FindingMapper
from tests.unit.schema_v2_projection.support import graph_with_source


class CandidateProjectionTests(unittest.TestCase):
    def test_enum_relations_and_partial_knowledge_keep_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            values = graph_with_source(Path(directory))
            index = SnapshotIndex.build(*values[2:9])
            builder = EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(directory)))
            original = values[3].evidence[0]
            items = [replace(original, id=stable_id(kind), kind=kind) for kind in ("enum_declaration", "enum_member_declaration", "enum_member_reference", "constexpr_condition", "call_expression")]
            evidence = {item.id: item for item in items}
            steps = {item.id: builder._evidence_step(item) for item in items}
            for kind, metadata in (("selects", {}), ("contains", {}), ("guarded_by", {"enumDependency": True})):
                relation = Relation(stable_id(kind), kind, stable_id("a"), stable_id("b"), tuple(evidence), "high", "partial", metadata)
                # Evidence kinds alone are no longer accepted as endpoint proof.
                unbound = replace(index, evidence=evidence, relations={relation.id: relation})
                self.assertEqual((), SourceChainIndex(unbound).query(items[0].id).arcs)
            entry = next(iter(index.knowledge.values()))
            missing = []
            self.assertEqual([], builder._knowledge_steps((stable_id("missing"),), missing))
            index = replace(index, knowledge={entry.id: replace(entry, source_ids=(stable_id("unknown-source"),))})
            self.assertEqual([], EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(directory)))._knowledge_steps((entry.id,), missing))
            self.assertEqual(2, len(missing))
            self.assertEqual("inactive", _relation_completion("not_selected"))
            self.assertEqual("complete", _relation_completion("selected"))
            inactive = builder._evidence_step(replace(original, metadata={"selectionStatus": "inactive"}))
            self.assertEqual("inactive", inactive.status)

    def test_labels_use_exact_applicable_knowledge(self):
        entries = [S(canonical_value="_mm_real", architecture_family="x86", fact_kind="intrinsics"),
                   S(canonical_value="__builtin_real", architecture_family="x86", fact_kind="builtins"),
                   S(canonical_value="CRC32", architecture_family="x86", fact_kind="targetFeatures"),
                   S(canonical_value="foreign", architecture_family="arm", fact_kind="intrinsics")]
        symbols = intrinsic_symbols(entries)
        self.assertEqual({"_mm_real", "__builtin_real"}, set(symbols))
        for kind, value, expected in [("call_expression", "_mm_real", True), ("symbol", "__builtin_real", True),
            ("call_expression", "_mm_unknown", False), ("call_expression", "CRC32", False),
            ("comment", "_mm_real", False), ("call_expression", [], False)]:
            self.assertEqual(expected, is_intrinsic(S(kind=kind, value=value), symbols))

    def test_unknown_candidate_has_neutral_main_fact_and_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            values = list(graph_with_source(Path(directory)))
            old = values[3].evidence[0]
            plain = replace(old, kind="call_expression", value="archive_sha512_update")
            known = replace(old, id=stable_id("known-call"), kind="call_expression")
            values[3] = replace(values[3], evidence=(plain, known))
            observation = replace(values[7].observations[0], status="candidate", kind="architecture_identifier_candidate",
                evidence_ids=(plain.id, known.id), metadata={"matchedEvidenceIds": (plain.id,)})
            classification = replace(values[7].classifications[0], impact="unknown", evidence_ids=(plain.id, known.id), metadata={"completeness": "unknown"})
            values[7] = replace(values[7], observations=(observation,), classifications=(classification,))
            index = SnapshotIndex.build(*values[2:9])
            source = SourceContextProjector(Path(directory))
            builder = EvidenceChainBuilder(index, values[2], source)
            finding = V2FindingMapper(index, builder, source).map(values[7])[0]
            self.assertEqual("archive_sha512_update", finding.fact.symbol)
            self.assertEqual("architecture_probe", finding.fact.kind)
            self.assertEqual("unknown", finding.conclusion.status)
            self.assertEqual("unknown", finding.evidenceChain.status)
            self.assertIn("当前证据不足", finding.conclusion.suggestion)
            self.assertIn("cannot be determined", finding.conclusion.suggestion_en)
            by_symbol = {step.symbol: step.kind for step in finding.evidenceChain.steps if step.source}
            self.assertEqual("source_evidence", by_symbol[plain.value])
            self.assertEqual("intrinsic_call", by_symbol[known.value])
            self.assertFalse(any(edge.kind == "alternative_to" for edge in finding.evidenceChain.edges))
            self.assertEqual("source_evidence", builder._evidence_step(replace(plain, value="_mm_fake")).kind)

    def test_same_kind_is_not_an_alternative_but_explicit_endpoints_are(self):
        with tempfile.TemporaryDirectory() as directory:
            values = list(graph_with_source(Path(directory)))
            first = values[3].evidence[0]
            second = replace(first, id=stable_id("second"), value="other_function", kind="call_expression")
            values[3] = replace(values[3], evidence=(first, second))
            classification = replace(values[7].classifications[0], evidence_ids=(first.id, second.id))
            index = SnapshotIndex.build(*values[2:9])
            builder = EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(directory)))
            steps = {item.id: builder._evidence_step(item) for item in (first, second)}
            source = Entity(stable_id("branch1"), "branch", "x86", properties={"sourceEvidenceId": first.id})
            target = Entity(stable_id("branch2"), "branch", "generic", properties={"sourceEvidenceId": second.id})
            relation = Relation(stable_id("alt"), "alternative_to", source.id, target.id, (second.id, first.id), "high", "complete")
            self.assertEqual((), SourceChainIndex(replace(index, relations={relation.id: relation})).query(first.id).arcs)
            index = replace(index, entities={source.id: source, target.id: target}, relations={**index.relations, relation.id: relation})
            classification = replace(classification, relation_ids=(*classification.relation_ids, relation.id))
            chain = EvidenceChainBuilder(index, values[2], SourceContextProjector(Path(directory))).build(classification)
            self.assertEqual(1, sum(edge.kind == "alternative_to" for edge in chain.edges))
