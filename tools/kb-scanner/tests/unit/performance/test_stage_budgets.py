from dataclasses import replace
import unittest

from kb_scanner.analyzers import BuildProofBudgets, BuildSelectionAnalyzer, TestAssetAnalyzer, TestProofBudgets, TestSelectionAnalyzer
from kb_scanner.core import AnalysisSnapshot, Entity, ProofPath, Relation, stable_id
from tests.unit.classification_assessment.support import context, knowledge, test_facts


def inherited(facts, count):
    node = Entity(stable_id("inherited"), "symbol", "unrelated")
    edges = tuple(Relation(stable_id("inherited-edge", i), "calls", node.id, node.id) for i in range(count))
    proofs = tuple(ProofPath(stable_id("inherited-proof", i), node.id, node.id, (edge.id,)) for i, edge in enumerate(edges))
    return AnalysisSnapshot(edges, (*facts.entities, node), proofs)


class StageBudgetTests(unittest.TestCase):
    def test_inherited_graph_does_not_consume_build_or_test_budgets(self):
        facts, kb = test_facts(), knowledge("-mavx")
        for analyzer in (BuildSelectionAnalyzer(BuildProofBudgets(2, 1)),
                         TestAssetAnalyzer(TestProofBudgets(max_relations=2))):
            outputs = []
            for count in (0, 20):
                base = inherited(facts, count)
                result = analyzer.analyze(context(), facts, kb, base)
                outputs.append((tuple(r for r in result.value.relations if r.id not in {r.id for r in base.relations}),
                                tuple(p for p in result.value.proof_paths if p.id not in {p.id for p in base.proof_paths}), result.diagnostics))
            self.assertEqual(outputs[0], outputs[1])
        assets = TestAssetAnalyzer().analyze(context(), facts, kb).value
        outputs = []
        for count in (0, 20):
            unrelated = inherited(facts, count)
            base = AnalysisSnapshot((*assets.relations, *unrelated.relations), (*assets.entities, unrelated.entities[-1]), unrelated.proof_paths)
            result = TestSelectionAnalyzer(TestProofBudgets(max_relations=2, max_paths=1)).analyze(context(), facts, kb, base)
            outputs.append((tuple(r for r in result.value.relations if r.id not in {r.id for r in base.relations}),
                            tuple(p for p in result.value.proof_paths if p.id not in {p.id for p in base.proof_paths}), result.diagnostics))
        self.assertEqual(outputs[0], outputs[1])
        self.assertTrue(any(d.code == "test-selection.max-paths" for d in outputs[1][2]))
