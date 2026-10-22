from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from kb_scanner.core import AnalysisSnapshot, DetectionSnapshot, ClassificationSnapshot, CompletionStatus, Observation, NormalizedSnapshot, NormalizedFact, KnowledgeSnapshot, KnowledgeEntry, Relation, Entity, FrontendSnapshot, stable_id
from kb_scanner.core.candidate_contract import architecture_attribute, invalid_candidate, validate_candidates
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
from kb_scanner.projection.projector import CompatibleReportProjector
from kb_scanner.projection.v2.projector import SchemaV2ReportProjector
from kb_scanner.assessors import MigrationAssessor
from tests.unit.schema_v2_projection.support import graph_with_source
from .support import make_entity, make_evidence, make_context


def candidate(**metadata):
    return Observation(stable_id('observation', metadata), 'unit', 'inline_asm_candidate', (stable_id('e'),), status='candidate', metadata={'candidateBasis': 'unclassified_inline_asm', 'architectureDisposition': 'unknown', **metadata})


class CandidateContractTests(unittest.TestCase):
    def test_attribute_names_not_generic_strings(self):
        for text in ('__attribute__((target("avx2")))', '[[gnu::target_clones("default", "avx2")]]', '__attribute__((vector_size(16)))', '__attribute__((__target__("new")))', '__declspec(cpu_specific(core_2_duo))'):
            self.assertTrue(architecture_attribute(text), text)
        for text in ('__attribute__((no_sanitize("memory")))', '__attribute__((annotate("target(avx2)")))', '__attribute__((aligned(32)))', '__declspec(dllexport)', '__attribute__((annotate("avx2")))', '__attribute__((no_sanitize("memory") /* target("avx2") */))'):
            self.assertFalse(architecture_attribute(text), text)

    def test_contract_preserves_other_candidates_and_rejects_invalid_structural_inputs(self):
        good = candidate()
        self.assertFalse(invalid_candidate(good))
        self.assertFalse(invalid_candidate(replace(good, status='confirmed_local', metadata={})))
        self.assertFalse(invalid_candidate(replace(good, kind='architecture_enum_candidate', metadata={})))
        self.assertFalse(invalid_candidate(replace(good, kind='target_attribute_candidate', metadata={'candidateBasis': 'architecture_attribute', 'architectureDisposition': 'x86', 'branchRole': 'x86'})))
        for item in (replace(good, metadata={}), replace(good, evidence_ids=()), candidate(architectureDisposition='foreign'), candidate(architectureDisposition='x86'), candidate(architectureDisposition='not-architecture-related'), candidate(architectureDisposition='duplicate-child'), candidate(candidateBasis='child')):
            self.assertTrue(invalid_candidate(item))
            with self.assertRaisesRegex(ValueError, 'candidate.invalid-admission'):
                DEFAULT_CLASSIFICATION_POLICY.decide(item, proof_complete=False, relation_unknown=False)

    def test_classifier_rejection_does_not_add_unknown_or_assessment_input(self):
        items = (candidate(architectureDisposition='foreign'), candidate())
        result = MigrationClassifier().classify(None, DetectionSnapshot(items), AnalysisSnapshot())
        self.assertEqual(1, len(result.value.classifications))
        self.assertEqual((items[1].id,), result.value.classifications[0].observation_ids)
        self.assertEqual({'classifier.invalid-candidate-admission', 'classifier.unknown-results'}, {x.code for x in result.diagnostics})
        rejected = MigrationClassifier().classify(None, DetectionSnapshot(items[:1]), AnalysisSnapshot())
        self.assertEqual(CompletionStatus.COMPLETE, rejected.status)
        self.assertEqual((), rejected.value.classifications)
        self.assertFalse(rejected.diagnostics[0].affects_exit_code)
        self.assertEqual((), rejected.value.observations)
        self.assertEqual(MigrationAssessor().assess(None, ClassificationSnapshot(), AnalysisSnapshot()), MigrationAssessor().assess(None, rejected.value, AnalysisSnapshot()))

    def test_projectors_fail_closed_on_bypassed_classifier_and_keep_existing_reports(self):
        with tempfile.TemporaryDirectory() as raw:
            args = list(graph_with_source(Path(raw)))
            invalid = candidate(architectureDisposition='foreign')
            classification = replace(args[7].classifications[0], observation_ids=(invalid.id,))
            args[6] = DetectionSnapshot((invalid,))
            args[7] = ClassificationSnapshot((invalid,), (classification,))
            args[0].output_dir.mkdir()
            existing = args[0].output_dir / 'scan-result.json'
            existing.write_text('old')
            for projector in (CompatibleReportProjector(), SchemaV2ReportProjector()):
                result = projector.project(*args)
                self.assertEqual(CompletionStatus.FAILED, result.status)
                self.assertTrue(result.diagnostics[0].affects_exit_code)
                self.assertEqual('projection.invalid-candidate-admission', result.diagnostics[0].code)
                self.assertEqual('old', existing.read_text())
            with self.assertRaisesRegex(ValueError, 'candidate.invalid-admission'):
                validate_candidates(args[6], args[7])
            validate_candidates(DetectionSnapshot(), ClassificationSnapshot((), (replace(classification, observation_ids=(stable_id('missing'),)),)))

    def test_detector_admission_and_confirmed_priority_with_fake_knowledge(self):
        entity = make_entity()
        branch = Entity(stable_id('branch'), 'branch', 'if:__aarch64__')
        for kind, value, foreign, confirmed, count in (
            ('inline_asm', 'asm("mystery")', False, False, 1),
            ('inline_asm', 'asm("mystery")', True, False, 0),
            ('inline_asm', 'asm("pause")', True, True, 1),
            ('declaration_attribute', '__attribute__((no_sanitize("memory")))', False, False, 0),
            ('declaration_attribute', '__attribute__((target("new")))', False, False, 1),
            ('declaration_attribute', '__attribute__((target("avx2")))', False, True, 1),
        ):
            evidence = make_evidence(entity, kind, value)
            fact = NormalizedFact(stable_id('fact'), kind, entity.id, value, 'scope', (evidence.id,))
            relation = Relation(stable_id('r'), 'guarded_by', entity.id, branch.id, (evidence.id,), status='complete', metadata={'architectureDisposition': 'foreign' if foreign else 'unknown'})
            entries = (KnowledgeEntry(stable_id('k'), 'assemblyInstructions' if kind == 'inline_asm' else 'targetFeatures', 'x86', 'pause' if kind == 'inline_asm' else 'avx2', (stable_id('s'),)),) if confirmed else ()
            knowledge = KnowledgeSnapshot(stable_id('k'), '1', entries=entries)
            result = LocalX86Detector(deferred_capabilities={}).detect(None, NormalizedSnapshot((entity,), (evidence,), (fact,)), AnalysisSnapshot((relation,), (entity, branch)), knowledge)
            self.assertEqual(count, len(result.value.observations), (kind, value, foreign))
            if count and not confirmed:
                self.assertFalse(invalid_candidate(result.value.observations[0]))

    def test_normalizer_full_root_distinct_spans_producers_and_contexts(self):
        entity = make_entity()
        first = make_evidence(entity, 'inline_asm', 'asm("' + 'x' * 600 + '")')
        second = replace(first, id=stable_id('second'), producer='clang')
        different = make_evidence(entity, 'inline_asm', first.value, line=2)
        result = CppEvidenceNormalizer().normalize(make_context(Path('/tmp')), FrontendSnapshot((entity,), (first, second, different))).value
        self.assertEqual(2, len(result.facts))
        self.assertTrue(all(len(x.canonical_value) > 600 for x in result.facts))
        merged = next(x for x in result.facts if len(x.evidence_ids) == 2)
        self.assertEqual({'test', 'clang'}, set(merged.producers))
        configured = tuple(replace(first, id=stable_id('config', name), metadata={'compilationContextId': stable_id('context', name)}) for name in ('a', 'b'))
        result = CppEvidenceNormalizer().normalize(make_context(Path('/tmp')), FrontendSnapshot((entity,), configured)).value
        self.assertEqual(2, len(result.facts))
        self.assertEqual({stable_id('context', name) for name in ('a', 'b')}, {x.context_ids[0] for x in result.facts})
