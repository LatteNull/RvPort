"""隔离用途 analyzer、Detector 关联及 composite 阶段顺序。"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest

from kb_scanner.core import AnalysisSnapshot, CompletionStatus, DetectionSnapshot, KnowledgeSnapshot, NormalizedFact, NormalizedSnapshot, StageResult, stable_id
from kb_scanner.core import CompilationUnitContext
from kb_scanner.frontends.cpp.compilation_database import compilation_context_id
from kb_scanner.assessors.migration import MigrationAssessor
from kb_scanner.analyzers.candidate_usage.analysis import CandidateUsageAnalyzer, CATALOG_KIND
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.classifiers.risk import present_risk
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.pipeline.composite import CompositeAnalyzer
from tests.unit.test_usage_session import inputs
from tests.unit.knowledge_detection.support import make_context
from tests.unit.classification_assessment.support import proof_analysis


def candidate_inputs():
    facts, root = inputs()
    candidate = NormalizedFact(root.fact_id, "enum_reference", root.subject_id, "X86", "occurrence",
        root.matched_evidence_ids)
    return replace(facts, facts=(*facts.facts, candidate)), root


class UsageAnalysisTests(unittest.TestCase):
    def test_compile_database_requires_exact_usage_configuration(self):
        facts, root = candidate_inputs()
        units = (CompilationUnitContext(Path('/tmp/a.c')), CompilationUnitContext(Path('/outside/b.c')),
                 CompilationUnitContext(Path('/tmp/other.c')))
        context = make_context(Path('/tmp'), compile_contexts=units)
        knowledge = KnowledgeSnapshot(stable_id('k'), '1')
        base = AnalysisSnapshot(entities=facts.entities)
        result = CandidateUsageAnalyzer().analyze(context, facts, knowledge, base)
        catalog = next(e for e in result.value.entities if e.kind == CATALOG_KIND)
        self.assertIn('usage-configuration-unknown', catalog.properties['entries'][0]['reasonCodes'])
        cfg = compilation_context_id(units[0], context.input_root)
        configured = replace(facts, facts=tuple(replace(f, metadata={**f.metadata, 'compilationContextId': cfg}) for f in facts.facts))
        result = CandidateUsageAnalyzer().analyze(context, configured, knowledge, base)
        catalog = next(e for e in result.value.entities if e.kind == CATALOG_KIND)
        self.assertEqual('complete', catalog.properties['entries'][0]['status'])

    def test_analysis_preserves_old_observation_and_only_removes_classification(self):
        facts, root = candidate_inputs()
        knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1")
        context = make_context(Path("/tmp"))
        base = AnalysisSnapshot(entities=facts.entities)
        before = LocalX86Detector(deferred_capabilities={}).detect(context, facts, base, knowledge)
        result = CandidateUsageAnalyzer().analyze(context, facts, knowledge, base)
        catalog = next(e for e in result.value.entities if e.kind == CATALOG_KIND)
        self.assertEqual(1, catalog.properties["rootCount"])
        self.assertEqual("complete", catalog.properties["entries"][0]["status"])
        preserved = {entity.id: entity for entity in result.value.entities}
        for entity in base.entities:
            self.assertEqual(entity, preserved[entity.id])
        after = LocalX86Detector(deferred_capabilities={}).detect(context, facts, result.value, knowledge)
        self.assertEqual(before.value, after.value)
        classified = MigrationClassifier().classify(context, after.value, result.value)
        self.assertFalse(classified.value.classifications)
        self.assertEqual(after.value.observations, classified.value.observations)
        self.assertTrue(facts.facts)
        repeated = CandidateUsageAnalyzer().analyze(context, replace(facts, facts=tuple(reversed(facts.facts))), knowledge, base)
        self.assertEqual(result, repeated)

    def test_no_demand_is_exact_passthrough_and_missing_scope_is_unknown(self):
        facts, _ = candidate_inputs()
        knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1")
        base = AnalysisSnapshot(entities=facts.entities)
        context = make_context(Path("/tmp"))
        no_demand = CandidateUsageAnalyzer(SimpleNamespace(select=lambda *_: ()))
        self.assertIs(base, no_demand.analyze(context, facts, knowledge, base).value)
        missing = replace(facts, facts=(facts.facts[-1],))
        result = CandidateUsageAnalyzer().analyze(context, missing, knowledge, base)
        self.assertFalse(result.value.proof_paths)
        catalog = next(e for e in result.value.entities if e.kind == CATALOG_KIND)
        self.assertEqual("unknown", catalog.properties["entries"][0]["status"])

    def test_composite_runs_usage_last_and_preserves_stage_failure(self):
        calls = []
        base = AnalysisSnapshot()
        def stage(name, status=CompletionStatus.COMPLETE):
            def analyze(*args):
                calls.append(name)
                return StageResult(None if status in {CompletionStatus.FAILED, CompletionStatus.UNAVAILABLE} else base, status)
            return SimpleNamespace(analyze=analyze)
        for status in (CompletionStatus.COMPLETE, CompletionStatus.PARTIAL, CompletionStatus.FAILED, CompletionStatus.UNAVAILABLE):
            calls.clear()
            analyzer = CompositeAnalyzer(*(stage(name) for name in ("source", "build", "assets", "tests", "family", "versions")),
                usage=stage("usage", status))
            result = analyzer.analyze(make_context(Path("/tmp")), NormalizedSnapshot(), KnowledgeSnapshot(stable_id("k"), "1"))
            self.assertEqual(status, result.status)
            self.assertEqual(["source", "build", "assets", "tests", "family", "versions", "usage"], calls)

    def test_exclusion_cannot_supply_build_target_or_alternative_evidence(self):
        facts, _ = candidate_inputs()
        context = make_context(Path("/tmp"))
        knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1")
        base = AnalysisSnapshot(entities=facts.entities)
        analysis = CandidateUsageAnalyzer().analyze(context, facts, knowledge, base).value
        detections = LocalX86Detector(deferred_capabilities={}).detect(context, facts, analysis, knowledge).value
        classified = MigrationClassifier().classify(context, detections, analysis).value
        self.assertFalse(classified.classifications)
        assessment = MigrationAssessor().assess(context, classified, analysis)
        project = next(item for item in assessment.value.assessments if item.kind == "project_migration_state")
        self.assertEqual("provisional", project.state)
        for dimension in ("input_completeness", "target_reachability", "riscv_or_generic_alternative"):
            self.assertEqual("unknown", project.metadata["dimensions"][dimension])
        self.assertFalse(project.metadata["compiled"])
        self.assertFalse(project.metadata["testsExecuted"])

    def test_original_high_blocker_and_execution_proof_survive_candidate_exclusion(self):
        facts, _ = candidate_inputs()
        context = make_context(Path("/tmp"))
        knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1")
        execution, confirmed = proof_analysis()
        base = replace(execution, entities=(*execution.entities, *facts.entities))
        analysis = CandidateUsageAnalyzer().analyze(context, facts, knowledge, base).value
        for field in ("entities", "relations", "proof_paths"):
            new = {item.id: item for item in getattr(analysis, field)}
            for item in getattr(base, field):
                self.assertEqual(item, new[item.id])
        # 使用已有已确认观察验证分类优先级，不用用途关系伪造执行观察。
        candidates = LocalX86Detector(deferred_capabilities={}).detect(context, facts,
            CandidateUsageAnalyzer().analyze(context, facts, knowledge, AnalysisSnapshot(entities=facts.entities)).value,
            knowledge).value.observations
        before = MigrationClassifier().classify(context, DetectionSnapshot((confirmed,)), base).value
        after = MigrationClassifier().classify(context, DetectionSnapshot((*candidates, confirmed)), analysis).value
        self.assertEqual(before.classifications, after.classifications)
        self.assertEqual("blocking_issue", after.classifications[0].impact)
        risk = present_risk(after.classifications[0], confirmed)
        self.assertEqual("high", risk.severity)
        self.assertTrue(risk.blocking)
        self.assertEqual((*candidates, confirmed), after.observations)
