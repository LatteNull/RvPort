"""消费精确 occurrence 的角色证明，不根据名称猜测用途。

默认用途 Analyzer 生成有界局部证明；缺失证据仍为 unknown，
此准入门禁不承担 codec/算法名称识别。
"""
from collections import defaultdict
from dataclasses import dataclass
from .usage_proof import UsageProofValidator


CANDIDATE_KINDS = frozenset({"architecture_enum_candidate", "architecture_identifier_candidate"})
DATA_ROLES = frozenset({"algorithm", "data_format", "output_platform", "non_execution_data"})


@dataclass(frozen=True)
class AdmissionDecision:
    status: str = "unknown"
    reason: str = "candidate-semantic-proof-unavailable"
    relation_ids: tuple[str, ...] = ()
    proof_ids: tuple[str, ...] = ()


class SemanticAdmissionIndex:
    def __init__(self, analysis):
        self.entities = {item.id: item for item in analysis.entities}
        self.relations = {item.id: item for item in analysis.relations}
        self.usage_validator = UsageProofValidator(self.entities, self.relations)
        self.roles = defaultdict(list)
        self.proofs = defaultdict(list)
        for item in analysis.relations:
            if item.kind == "has_semantic_role":
                self.roles[item.metadata.get("factId")].append(item)
        for proof in analysis.proof_paths:
            for rid in proof.relation_ids:
                if rid in self.relations and self.relations[rid].kind == "has_semantic_role":
                    self.proofs[rid].append(proof)

    def _complete(self, proof, role):
        if (proof.status != "complete" or proof.truncated or not proof.relation_ids or role.id not in proof.relation_ids
                or proof.source_id != role.source_id or proof.target_id != role.target_id):
            return False
        current = proof.source_id
        for rid in proof.relation_ids:
            relation = self.relations.get(rid)
            if (relation is None or relation.status != "complete" or relation.source_id != current
                    or relation.source_id not in self.entities or relation.target_id not in self.entities):
                return False
            current = relation.target_id
        return current == proof.target_id

    def decide(self, observation):
        if observation.status != "candidate" or observation.kind not in CANDIDATE_KINDS:
            return AdmissionDecision("not_applicable", "not-an-architecture-candidate")
        # Existing execution-dependency evidence takes precedence over data roles.
        if observation.metadata.get("enumDependencyKnowledgeIds") or observation.metadata.get("enumDependencyComplete") or any(
            relation.metadata.get("itemKind") == "source_x86_dependency" or relation.metadata.get("enumDependency")
            for rid in observation.relation_ids if (relation := self.relations.get(rid)) is not None
        ):
            return AdmissionDecision(reason="candidate-has-execution-evidence")
        configuration = observation.metadata.get("configuration", "default")
        fact_id = observation.metadata.get("factId")
        if not isinstance(fact_id, str) or not fact_id:
            return AdmissionDecision()
        roles = [r for r in self.roles.get(fact_id, ()) if r.metadata.get("configuration") == configuration]
        root_ids = set(observation.metadata.get("matchedEvidenceIds", ()))
        if not roles or not root_ids or not root_ids.issubset(observation.evidence_ids):
            return AdmissionDecision()
        if len(roles) > 64:
            return AdmissionDecision(reason="candidate-semantic-proof-budget")
        proof_ids = set()
        for relation in roles:
            target = self.entities.get(relation.target_id)
            proofs = self.proofs[relation.id]
            if (
                relation.status != "complete" or relation.source_id not in self.entities
                or relation.source_id != observation.metadata.get("subjectId")
                or relation.metadata.get("scope") != "occurrence"
                or relation.metadata.get("scopeComplete") is not True
                or not root_ids.issubset(relation.evidence_ids)
                or target is None or target.kind != "semantic_role" or target.name not in DATA_ROLES
                or not self.usage_validator.valid(relation, root_ids, configuration)
                or not proofs or not all(self._complete(proof, relation) for proof in proofs)
            ):
                return AdmissionDecision(reason="candidate-semantic-proof-incomplete-or-conflicting")
            proof_ids.update(proof.id for proof in proofs)
        return AdmissionDecision("excluded", "proven-non-execution-role", tuple(sorted(r.id for r in roles)), tuple(sorted(proof_ids)))
