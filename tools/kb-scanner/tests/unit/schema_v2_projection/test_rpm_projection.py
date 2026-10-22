import unittest
from dataclasses import replace
from kb_scanner.core import FrontendSnapshot, AssessmentSnapshot
from kb_scanner.analyzers import BuildSelectionAnalyzer
from kb_scanner.detectors import BuildSelectionDetector
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.projection.v2.index import SnapshotIndex
from kb_scanner.projection.v2.chain import EvidenceChainBuilder
from kb_scanner.projection.v2.mapper import V2FindingMapper
from kb_scanner.projection.v2.context import SourceContextProjector
from tests.unit.build_selection.test_rpm_graph import normalized, record
from tests.unit.build_selection.support import context, flag_knowledge


class RpmProjectionTests(unittest.TestCase):
    def test_primary_fact_and_edges_use_real_occurrence_endpoints(self):
        ctx = context()
        knowledge = flag_knowledge()
        facts = normalized([record('a', 'build_arch_probe', '%{_arch}'),
                            record('bb', 'build_branch', '%if 0', ('a',), state='inactive'),
                            record('ccc', parents=('bb',), state='inactive', x86Confirmed=True)])
        analysis = BuildSelectionAnalyzer().analyze(ctx, facts, knowledge).value
        detections = BuildSelectionDetector().detect(ctx, facts, analysis, knowledge).value
        classified = MigrationClassifier().classify(ctx, detections, analysis).value
        index = SnapshotIndex.build(knowledge, FrontendSnapshot(facts.entities, facts.evidence), facts,
                                    analysis, detections, classified, AssessmentSnapshot())
        source = SourceContextProjector(ctx.input_root, reader=lambda _: '\n%{_arch}\n%if 0\nfoo(x86-64)\n')
        builder = EvidenceChainBuilder(index, knowledge, source)
        finding = V2FindingMapper(index, builder, source).map(classified)[0]
        self.assertEqual('foo(x86-64)', finding.fact.symbol)
        self.assertEqual(4, finding.fact.primaryLocation.span.start.line)
        self.assertTrue(finding.fact.primaryLocation.context.highlights)
        self.assertIn('org.rvport.kb-scanner.rpm', finding.fact.extensions)
        self.assertTrue(all(o.extensions for o in finding.occurrences))
        chain = finding.evidenceChain
        steps = {step.id: step for step in chain.steps}
        ordered = [steps[sid].symbol for sid in chain.primaryPath if steps[sid].source]
        self.assertEqual(['%{_arch}', '%if 0', 'foo(x86-64)'], ordered)
        for left, right in zip(chain.primaryPath, chain.primaryPath[1:]):
            self.assertTrue(any(edge.fromStepId == left and edge.toStepId == right for edge in chain.edges))
        relations = {r.id:r for r in analysis.relations}
        for edge in chain.edges:
            if not steps[edge.fromStepId].source or not steps[edge.toStepId].source:
                continue
            relation = relations[edge.provenance[0].id]
            self.assertEqual(index.entities[relation.source_id].properties['sourceEvidenceId'], steps[edge.fromStepId].provenance[0].id)
            self.assertEqual(index.entities[relation.target_id].properties['sourceEvidenceId'], steps[edge.toStepId].provenance[0].id)
        # Missing/truncated proofs stay representable, never invent a source edge.
        damaged = replace(classified.classifications[0], impact='unknown', proof_path_ids=(), metadata={'completeness':'unknown'})
        broken = builder.build(damaged)
        self.assertTrue(broken.breaks)
        self.assertEqual('unknown', broken.status)
