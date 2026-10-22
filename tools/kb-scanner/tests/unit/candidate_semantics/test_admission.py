from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as S
import unittest

from kb_scanner.core import AnalysisSnapshot, DetectionSnapshot, Entity, Observation, ProofPath, Relation, stable_id
from kb_scanner.classifiers.semantic_admission import SemanticAdmissionIndex
from kb_scanner.classifiers.migration import MigrationClassifier
from tests.unit.knowledge_detection.support import make_context
from tests.unit.test_usage_proofs import proof_inputs
from kb_scanner.analyzers.candidate_usage.proofs import materialize


def inputs(role="data_format"):
    facts, root, session, resolution, scope_facts = proof_inputs()
    emitted_entities, emitted_relations, emitted_proofs, summary = materialize(root, resolution, session, scope_facts)
    subject = facts.entities[0]
    target = Entity(stable_id("role", role), "semantic_role", role)
    eid, fid = root.matched_evidence_ids[0], root.fact_id
    original = next(relation for relation in emitted_relations if relation.kind == "has_semantic_role")
    relation = replace(original, id=stable_id("role-relation", role), target_id=target.id)
    proof = ProofPath(stable_id("role-proof", role), subject.id, target.id, (relation.id,), "complete")
    observation = Observation(stable_id("observation"), "C_CPP.X86.ARCH_MACRO_CANDIDATE", "architecture_identifier_candidate", (eid,), (relation.id,), "medium", "candidate",
        {"factId": fid, "subjectId": subject.id, "matchedEvidenceIds": (eid,), "configuration": "default", "candidateBasis": "architecture-shaped-identifier", "architectureDisposition": "unknown"})
    return observation, AnalysisSnapshot(relations=(relation, *(r for r in emitted_relations if r.kind != "has_semantic_role")),
        entities=(subject, target, *(e for e in emitted_entities if e.kind != "semantic_role")), proof_paths=(proof,))


class SemanticAdmissionTests(unittest.TestCase):
    def test_complete_data_roles_filter_classification_not_observation(self):
        for role in ("algorithm", "data_format", "output_platform", "non_execution_data"):
            obs, analysis = inputs(role)
            decision = SemanticAdmissionIndex(analysis).decide(obs)
            self.assertEqual("excluded", decision.status)
            result = MigrationClassifier().classify(make_context(Path("/project")), DetectionSnapshot((obs,)), analysis)
            self.assertEqual((), result.value.classifications)
            self.assertEqual((obs,), result.value.observations)
            diagnostic = next(d for d in result.diagnostics if d.code == "classifier.candidate-semantic-exclusions")
            self.assertEqual(1, diagnostic.details["count"])
            self.assertEqual(decision.proof_ids, diagnostic.details["exclusions"][0]["proofIds"])

    def test_absence_is_unknown_not_safe(self):
        obs, _ = inputs()
        obs = replace(obs, relation_ids=())
        analysis = AnalysisSnapshot()
        result = MigrationClassifier().classify(make_context(Path("/project")), DetectionSnapshot((obs,)), analysis)
        self.assertEqual("unknown", result.value.classifications[0].impact)
        self.assertEqual("unknown", result.value.classifications[0].metadata["completeness"])
        self.assertEqual((obs,), result.value.observations)

    def test_unclosed_or_conflicting_roles_do_not_filter(self):
        obs, a = inputs()
        r, p = a.relations[0], a.proof_paths[0]
        bad_relations = [replace(r, status="partial"), replace(r, source_id=stable_id("missing")),
            replace(r, source_id=a.entities[1].id), replace(r, evidence_ids=()),
            replace(r, metadata={**r.metadata, "scopeComplete": False}),
            replace(r, metadata={**r.metadata, "scope": "file"}),
            replace(r, metadata={**r.metadata, "configuration": "another"}),
            replace(r, metadata={**r.metadata, "factId": stable_id("another-fact")}),
            replace(r, target_id=stable_id("missing"))]
        for bad in bad_relations:
            with self.subTest(relation=bad):
                self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, relations=(bad,))).decide(obs).status)
        for target in (replace(a.entities[1], kind="symbol"), replace(a.entities[1], name="execution_architecture")):
            self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, entities=(a.entities[0], target))).decide(obs).status)
        for proof in (replace(p, status="partial"), replace(p, source_id=a.entities[1].id), replace(p, target_id=a.entities[0].id),
                      replace(p, relation_ids=(stable_id("missing"), r.id)), replace(p, relation_ids=(r.id, r.id))):
            self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, proof_paths=(proof,))).decide(obs).status)
        self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, proof_paths=())).decide(obs).status)
        self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, proof_paths=(p, replace(p, id=stable_id("partial"), status="partial")))).decide(obs).status)

    def test_scope_root_and_known_execution_are_not_overridden(self):
        obs, a = inputs()
        for metadata in ({}, {**obs.metadata, "matchedEvidenceIds": (stable_id("other"),)},
                         {**obs.metadata, "enumDependencyKnowledgeIds": (stable_id("intrinsic"),)},
                         {**obs.metadata, "enumDependencyComplete": True}):
            self.assertEqual("unknown", SemanticAdmissionIndex(a).decide(replace(obs, metadata=metadata)).status)
        for other in (replace(obs, status="confirmed_local"), replace(obs, kind="inline_asm_candidate")):
            self.assertEqual("not_applicable", SemanticAdmissionIndex(a).decide(other).status)
        # Two missing IDs are not evidence that both objects describe one fact.
        for missing in (None, ""):
            unscoped = replace(obs, metadata={**obs.metadata, "factId": missing})
            relation = replace(a.relations[0], metadata={**a.relations[0].metadata, "factId": missing})
            self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, relations=(relation,))).decide(unscoped).status)
        r = a.relations[0]
        many = tuple(replace(r, id=stable_id("role", i)) for i in range(65))
        self.assertEqual("candidate-semantic-proof-budget", SemanticAdmissionIndex(replace(a, relations=many)).decide(obs).reason)

    def test_non_role_relations_and_disconnected_paths(self):
        obs, a = inputs()
        r, p = a.relations[0], a.proof_paths[0]
        other = replace(r, id=stable_id("other"), kind="contains", source_id=r.target_id, target_id=r.source_id)
        index = SemanticAdmissionIndex(replace(a, relations=(r, other)))
        self.assertFalse(index._complete(replace(p, relation_ids=(r.id, other.id)), r))
        self.assertEqual("unknown", SemanticAdmissionIndex(replace(a, relations=(other,))).decide(obs).status)

    def test_execution_relations_and_mixed_roles_prevent_exclusion(self):
        obs, a = inputs()
        r = a.relations[0]
        for metadata in ({"itemKind": "source_x86_dependency"}, {"enumDependency": True}):
            dependency = replace(r, id=stable_id("execution"), kind="selects", status="selected", metadata=metadata)
            both = replace(a, relations=(*a.relations, dependency))
            linked = replace(obs, relation_ids=(*obs.relation_ids, dependency.id))
            self.assertEqual("candidate-has-execution-evidence", SemanticAdmissionIndex(both).decide(linked).reason)
        other_obs, execution = inputs("execution_architecture")
        both = replace(a, entities=(*a.entities, execution.entities[1]), relations=(*a.relations, *execution.relations), proof_paths=(*a.proof_paths, *execution.proof_paths))
        self.assertEqual("unknown", SemanticAdmissionIndex(both).decide(obs).status)
