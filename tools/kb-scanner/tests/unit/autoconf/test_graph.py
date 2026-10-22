import unittest
from dataclasses import replace

from kb_scanner.analyzers.autoconf_selection import analyze_autoconf
from kb_scanner.analyzers.build_selection import BuildSelectionAnalyzer, BuildProofBudgets
from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
from kb_scanner.core import AnalysisSnapshot, CompletionStatus, Entity, Evidence, FrontendSnapshot, NormalizedFact, NormalizedSnapshot, stable_id
from kb_scanner.detectors.build_selection import BuildSelectionDetector
from kb_scanner.normalization.build import BuildEvidenceNormalizer
from tests.unit.build_selection.support import context, flag_knowledge


def snapshot(*entries):
    entity = Entity(stable_id("file"), "build_file", "configure")
    evidence, facts = [], []
    for key, properties in entries:
        metadata = {"autoconf": {"key": key, "unit": "configure", "digest": "abc", **properties}, "role": "x86"}
        evidence.append(Evidence(stable_id("e" + key), "build_branch", entity.id, "x86*", "test", "static-build", "high", metadata=metadata))
        facts.append(NormalizedFact(stable_id("f" + key), "build_branch", entity.id, "x86*", "autoconf:" + key, (stable_id("e" + key),), metadata=metadata))
    return NormalizedSnapshot((entity,), tuple(evidence), tuple(facts))


class GraphTests(unittest.TestCase):
    def test_normalizer_preserves_scope_and_metadata_without_coalescing_events(self):
        inputs = snapshot(("a", {"parents": ()}), ("b", {"parents": ("a",)}))
        result = BuildEvidenceNormalizer().normalize(context(), FrontendSnapshot(inputs.entities, inputs.evidence))
        self.assertEqual(len(result.value.facts), 2)
        self.assertEqual({f.scope for f in result.value.facts}, {"autoconf:a", "autoconf:b"})
        self.assertTrue(all("autoconf" in f.metadata for f in result.value.facts))

    def test_source_chain_complete_rejection_nonblocking_and_old_gap_excluded(self):
        facts = snapshot(("a", {"entry": True}), ("b", {"parents": ("a",)}),
                         ("end", {"parents": ("b",), "outcome": "rejected", "bound": True, "reason": "autoconf-explicit-rejection"}),
                         ("raw", {"raw": True}))
        result = BuildSelectionAnalyzer().analyze(context(), facts, flag_knowledge())
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual(len(result.value.relations), 3)
        self.assertTrue(all("autoconf" in item.metadata for item in result.value.relations))
        observations = BuildSelectionDetector().detect(context(), facts, result.value, flag_knowledge()).value.observations
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].kind, "missing_riscv_selection_path")
        decision = DEFAULT_CLASSIFICATION_POLICY.decide(observations[0], proof_complete=True, relation_unknown=False)
        self.assertEqual(decision.impact, "actionable_non_blocking")
        terminal = next(path for path in result.value.proof_paths if len(path.relation_ids) == 3)
        self.assertEqual(terminal.status, "complete")
        self.assertEqual(observations[0].metadata["matchedEvidenceIds"], (stable_id("eend"),))

    def test_unknown_unbound_rejection_and_positive_no_finding(self):
        for outcome, bound, expected in (("unknown", True, 1), ("rejected", False, 1), ("accepted", False, 0), ("", False, 0)):
            facts = snapshot(("a", {"outcome": outcome, "bound": bound, "reason": "uncertain" if outcome == "unknown" else ""}))
            analysis = analyze_autoconf(context(), facts, AnalysisSnapshot(), 100, 100).value
            observations = BuildSelectionDetector().detect(context(), facts, analysis, flag_knowledge()).value.observations
            self.assertEqual(len(observations), expected)
            if expected:
                self.assertEqual(observations[0].kind, "build_selection_unknown")
                self.assertEqual(DEFAULT_CLASSIFICATION_POLICY.decide(observations[0], proof_complete=False, relation_unknown=True).impact, "unknown")

    def test_broken_parent_cycle_budget_and_existing_graph_remain_safe(self):
        for entries, reason in ((("a", {"parents": ("missing",), "outcome": "rejected", "bound": True}),), "parent-missing"),:
            facts = snapshot(*entries)
            result = analyze_autoconf(context(), facts, AnalysisSnapshot(), 100, 100)
            self.assertTrue(any(reason in item.message for item in result.diagnostics))
            self.assertTrue(all(item.status == "unknown" for item in result.value.proof_paths))
            self.assertFalse(any(item.metadata.get("issue") for item in result.value.relations))
        facts = snapshot(("a", {"parents": ("b",)}), ("b", {"parents": ("a",)}))
        result = analyze_autoconf(context(), facts, AnalysisSnapshot(), 100, 100)
        self.assertTrue(any("cycle" in item.message for item in result.diagnostics))
        facts = snapshot(("a", {}), ("b", {"parents": ("a",)}))
        for relations, paths in ((0, 100), (100, 0), (1, 1)):
            result = analyze_autoconf(context(), facts, AnalysisSnapshot(), relations, paths)
            self.assertTrue(any("budget" in item.message for item in result.diagnostics))
            self.assertLessEqual(len(result.value.relations), relations)
        invalid = replace(facts, entities=())
        self.assertEqual(BuildSelectionAnalyzer().analyze(context(), invalid, flag_knowledge()).status, CompletionStatus.FAILED)

    def test_exhausted_proofs_preserve_bounded_unknown_relations_and_findings(self):
        for outcome in ("rejected", "unknown"):
            facts = snapshot(("entry", {}), ("end", {"parents": ("entry",), "bound": True, "outcome": outcome}))
            result = analyze_autoconf(context(), facts, AnalysisSnapshot(), 10, 0)
            self.assertEqual(len(result.value.relations), 2)
            self.assertFalse(result.value.proof_paths)
            self.assertTrue(all(relation.status == "unknown" for relation in result.value.relations))
            detected = BuildSelectionDetector().detect(context(), facts, result.value, flag_knowledge()).value
            self.assertEqual([item.kind for item in detected.observations], ["build_selection_unknown"])
