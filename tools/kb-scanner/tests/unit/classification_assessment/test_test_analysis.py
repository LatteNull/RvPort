from __future__ import annotations

import unittest
from dataclasses import replace

from kb_scanner.analyzers import TestAssetAnalyzer, TestProofBudgets, TestSelectionAnalyzer
from kb_scanner.core import (
    AnalysisSnapshot,
    CompletionStatus,
    Entity,
    Evidence,
    NormalizedFact,
    NormalizedSnapshot,
    ProofPath,
    Relation,
    stable_id,
)
from tests.unit.classification_assessment.support import context, knowledge, test_facts


class TestAnalysisTests(unittest.TestCase):
    def test_missing_source_entity_is_recovered_for_confirmed_test_target(self) -> None:
        facts = test_facts(include_x86=False)
        facts = replace(facts, entities=(facts.entities[0],))
        result = TestAssetAnalyzer().analyze(context(), facts, knowledge())
        self.assertEqual(CompletionStatus.COMPLETE, result.status)
        recovered = next(item for item in result.value.entities if item.kind == "test_source")
        self.assertEqual("tests/test_math.c", recovered.name)
        self.assertTrue(any(item.kind == "contains_test" and item.target_id == recovered.id for item in result.value.relations))

    def test_other_configuration_and_unresolved_explicit_links_do_not_create_edges(self) -> None:
        facts = test_facts(include_x86=False)
        for fields in ({"configuration": "other"}, {"coverageTarget": "absent.c", "alternativeTestFor": "absent-test"}):
            with self.subTest(fields=fields):
                source = replace(facts.facts[1], metadata={**facts.facts[1].metadata, **fields})
                changed = replace(facts, facts=(facts.facts[0], source))
                assets = TestAssetAnalyzer().analyze(context(), changed, knowledge()).value
                result = TestSelectionAnalyzer().analyze(context(), changed, knowledge(), assets)
                self.assertFalse(any(item.kind in {"covers_candidate", "alternative_test_for"} for item in result.value.relations))
                if "configuration" in fields:
                    self.assertFalse(any(item.kind == "exercises" for item in result.value.relations))

    def test_ctest_target_source_and_x86_dependency_have_stable_bounded_proof(self) -> None:
        facts = test_facts()
        first = TestAssetAnalyzer().analyze(context(), facts, knowledge("-mavx"))
        self.assertEqual(first.status, CompletionStatus.COMPLETE)
        self.assertTrue(any(item.kind == "test_suite" for item in first.value.entities))
        self.assertTrue(any(item.kind == "test_target" for item in first.value.entities))
        self.assertTrue(any(item.kind == "contains_test" for item in first.value.relations))
        second = TestSelectionAnalyzer().analyze(context(), facts, knowledge("-mavx"), first.value)
        self.assertEqual(second.status, CompletionStatus.COMPLETE)
        exercise = next(item for item in second.value.relations if item.kind == "exercises" and item.metadata.get("x86Dependency"))
        self.assertEqual(exercise.status, "selected")
        self.assertTrue(exercise.metadata["knowledgeIds"])
        proof = next(item for item in second.value.proof_paths if exercise.id in item.relation_ids)
        self.assertEqual(proof.status, "complete")
        again = TestSelectionAnalyzer().analyze(context(), facts, knowledge("-mavx"), first.value)
        self.assertEqual(second.value, again.value)

    def test_same_file_local_fact_does_not_become_test_execution_proof(self) -> None:
        facts = test_facts(include_x86=False)
        source = facts.entities[1]
        local_evidence = Evidence(stable_id("local-x86-evidence"), "call", source.id, "_mm_add_epi32", "unit", "syntax", "high")
        local_fact = NormalizedFact(
            stable_id("local-x86-fact"), "call", source.id, "_mm_add_epi32", "source:tests/test_math.c:1",
            (local_evidence.id,), producers=("unit",),
        )
        enriched = NormalizedSnapshot(facts.entities, (*facts.evidence, local_evidence), (*facts.facts, local_fact))
        kb = knowledge("_mm_add_epi32")
        assets = TestAssetAnalyzer().analyze(context(), enriched, kb).value
        result = TestSelectionAnalyzer().analyze(context(), enriched, kb, assets)
        self.assertFalse(any(item.metadata.get("factId") == local_fact.id for item in result.value.relations))
        self.assertIn(local_fact, enriched.facts)
        self.assertIn(local_evidence, enriched.evidence)

    def test_inactive_and_unknown_selection_are_not_promoted(self) -> None:
        inactive_facts = test_facts(status="inactive")
        assets = TestAssetAnalyzer().analyze(context(), inactive_facts, knowledge("-mavx")).value
        inactive = TestSelectionAnalyzer().analyze(context(), inactive_facts, knowledge("-mavx"), assets)
        self.assertEqual({item.status for item in inactive.value.relations if item.kind == "exercises"}, {"inactive"})
        unknown_facts = test_facts(status="unknown")
        unknown_assets = TestAssetAnalyzer().analyze(context(), unknown_facts, knowledge("-mavx"))
        self.assertEqual(unknown_assets.status, CompletionStatus.COMPLETE)
        unknown = TestSelectionAnalyzer().analyze(context(), unknown_facts, knowledge("-mavx"), unknown_assets.value)
        self.assertEqual(unknown.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.status == "unknown" for item in unknown.value.relations if item.kind == "exercises"))

    def test_path_only_candidates_and_non_test_near_matches(self) -> None:
        candidate = test_facts(input_kind="make", target="contest", include_x86=False)
        result = TestAssetAnalyzer().analyze(context(), candidate, knowledge())
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.kind == "test_candidate" for item in result.value.entities))
        self.assertFalse(any(item.kind == "test_target" for item in result.value.entities))
        non_test = test_facts(input_kind="make", target="library", source_name="examples/test_avx.c", include_x86=False)
        result = TestAssetAnalyzer().analyze(context(), non_test, knowledge())
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertFalse(any(item.kind.startswith("test_") for item in result.value.entities))

    def test_rpm_check_section_is_confirmed_without_executing_recipe(self) -> None:
        subject = Entity(stable_id("rpm"), "build_file", "package.spec")
        evidence = Evidence(stable_id("rpm-e"), "build_package_section", subject.id, "check", "unit", "static-build", "high", metadata={"section": "check", "selectionStatus": "selected", "inputKind": "rpm"})
        fact = NormalizedFact(stable_id("rpm-f"), "build_package_section", subject.id, "check", "rpm:1", (evidence.id,), metadata=evidence.metadata)
        snapshot = NormalizedSnapshot((subject,), (evidence,), (fact,))
        result = TestAssetAnalyzer().analyze(context(), snapshot, knowledge())
        target = next(item for item in result.value.entities if item.kind == "test_target")
        self.assertEqual(target.name, "%check")
        self.assertEqual(target.properties["roleBasis"], "rpm-check-section")

    def test_explicit_coverage_metadata_only_creates_candidate_when_endpoint_exists(self) -> None:
        facts = test_facts(include_x86=False)
        implementation = Entity(stable_id("impl"), "source_file", "src/portable.c")
        source_fact = facts.facts[1]
        enhanced = NormalizedFact(
            source_fact.id,
            source_fact.kind,
            source_fact.subject_id,
            source_fact.canonical_value,
            source_fact.scope,
            source_fact.evidence_ids,
            metadata={**dict(source_fact.metadata), "coverageTarget": implementation.name},
        )
        enriched = NormalizedSnapshot((*facts.entities, implementation), facts.evidence, (facts.facts[0], enhanced))
        assets = TestAssetAnalyzer().analyze(context(), enriched, knowledge()).value
        result = TestSelectionAnalyzer().analyze(context(), enriched, knowledge(), assets)
        self.assertTrue(any(item.kind == "covers_candidate" and item.target_id == implementation.id for item in result.value.relations))

    def test_explicit_alternative_test_metadata_creates_relation_without_name_guessing(self) -> None:
        facts = test_facts(include_x86=False)
        subject = facts.entities[0]
        second_evidence = Evidence(
            stable_id("second-target-evidence"), "build_target", subject.id, "other-test", "unit", "static-build", "high",
            metadata={"inputKind": "ctest", "target": "other-test", "configuration": "cfg", "selectionStatus": "selected"},
        )
        second_fact = NormalizedFact(
            stable_id("second-target-fact"), "build_target", subject.id, "other-test", "unit:other",
            (second_evidence.id,), metadata=second_evidence.metadata,
        )
        source = facts.facts[1]
        linked_source = NormalizedFact(
            source.id, source.kind, source.subject_id, source.canonical_value, source.scope, source.evidence_ids,
            metadata={**dict(source.metadata), "alternativeTestFor": "other-test"},
        )
        enriched = NormalizedSnapshot(facts.entities, (*facts.evidence, second_evidence), (facts.facts[0], second_fact, linked_source))
        assets = TestAssetAnalyzer().analyze(context(), enriched, knowledge()).value
        result = TestSelectionAnalyzer().analyze(context(), enriched, knowledge(), assets)
        self.assertTrue(any(item.kind == "alternative_test_for" for item in result.value.relations))

    def test_invalid_references_fail_without_partial_graph(self) -> None:
        facts = test_facts()
        original = facts.facts[0]
        bad_fact = NormalizedFact(original.id, original.kind, stable_id("missing"), original.canonical_value, original.scope, original.evidence_ids, metadata=original.metadata)
        invalid = NormalizedSnapshot(facts.entities, facts.evidence, (bad_fact,))
        self.assertEqual(TestAssetAnalyzer().analyze(context(), invalid, knowledge()).status, CompletionStatus.FAILED)

        missing = stable_id("missing-evidence")
        relation = Relation(stable_id("bad-relation"), "selects_test", facts.entities[0].id, facts.entities[1].id, (missing,))
        base = AnalysisSnapshot((relation,), facts.entities)
        self.assertEqual(TestSelectionAnalyzer().analyze(context(), facts, knowledge(), base).status, CompletionStatus.FAILED)

        good_relation = Relation(stable_id("good-relation"), "contains_test", facts.entities[0].id, facts.entities[1].id, (facts.evidence[0].id,))
        bad_proof = ProofPath(stable_id("bad-proof"), facts.entities[0].id, facts.entities[1].id, (stable_id("missing-relation"),), "unknown", "missing")
        base = AnalysisSnapshot((good_relation,), facts.entities, (bad_proof,))
        self.assertEqual(TestSelectionAnalyzer().analyze(context(), facts, knowledge(), base).status, CompletionStatus.FAILED)

    def test_budgets_validate_and_truncate_deterministically(self) -> None:
        with self.assertRaises(ValueError):
            TestProofBudgets(max_assets=0)
        facts = test_facts()
        asset_result = TestAssetAnalyzer(TestProofBudgets(max_assets=1)).analyze(context(), facts, knowledge())
        self.assertEqual(asset_result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.code == "test-selection.max-assets" for item in asset_result.diagnostics))
        assets = TestAssetAnalyzer().analyze(context(), facts, knowledge()).value
        path_limited = TestSelectionAnalyzer(TestProofBudgets(max_depth=1)).analyze(context(), facts, knowledge("-mavx"), assets)
        self.assertTrue(any(item.truncated for item in path_limited.value.proof_paths))
        relation_limited = TestSelectionAnalyzer(TestProofBudgets(max_relations=1)).analyze(context(), facts, knowledge("-mavx"), assets)
        self.assertEqual(relation_limited.status, CompletionStatus.PARTIAL)
        visit_limited = TestSelectionAnalyzer(TestProofBudgets(max_visited=1)).analyze(context(), facts, knowledge("-mavx"), assets)
        self.assertTrue(any(item.code == "test-selection.max-visited" for item in visit_limited.diagnostics))
        path_budget = TestSelectionAnalyzer(TestProofBudgets(max_paths=1)).analyze(context(), facts, knowledge("-mavx"), assets)
        self.assertTrue(any(item.code == "test-selection.max-paths" for item in path_budget.diagnostics))

        left, right = facts.entities
        cycle_one = Relation(stable_id("cycle-one"), "alternative_test_for", left.id, right.id, (facts.evidence[0].id,))
        cycle_two = Relation(stable_id("cycle-two"), "alternative_test_for", right.id, left.id, (facts.evidence[0].id,))
        cyclic = AnalysisSnapshot((cycle_one, cycle_two), facts.entities)
        cycle_result = TestSelectionAnalyzer().analyze(context(), facts, knowledge("-mavx"), cyclic)
        self.assertIn(cycle_one, cycle_result.value.relations)
        self.assertIn(cycle_two, cycle_result.value.relations)


if __name__ == "__main__":
    unittest.main()
