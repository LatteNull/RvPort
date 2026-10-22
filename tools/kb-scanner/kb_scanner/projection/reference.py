from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from ..core import Entity, Evidence, ProofPath, Relation


@dataclass(frozen=True, slots=True)
class ReferenceClosure:
    evidence_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    proof_path_ids: tuple[str, ...]
    missing_ids: tuple[str, ...] = ()
    conflicting_ids: tuple[str, ...] = ()
    truncated: bool = False

    @property
    def status(self) -> str:
        if self.truncated or self.conflicting_ids:
            return "partial"
        return "complete" if not self.missing_ids else "partial"

    @property
    def reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.missing_ids:
            reasons.append("missing-reference")
        if self.conflicting_ids:
            reasons.append("reference-type-conflict")
        if self.truncated:
            reasons.append("reference-budget-exceeded")
        return tuple(reasons)


class ReferenceClosureResolver:
    __slots__ = ("_evidence", "_entities", "_relations", "_proofs", "_max_references")

    def __init__(
        self,
        evidence: Mapping[str, Evidence],
        entities: Mapping[str, Entity],
        relations: Mapping[str, Relation],
        proofs: Mapping[str, ProofPath],
        *,
        max_references: int = 4096,
    ) -> None:
        if max_references < 1:
            raise ValueError("reference closure budget must be positive")
        self._evidence = evidence
        self._entities = entities
        self._relations = relations
        self._proofs = proofs
        self._max_references = max_references

    def resolve(
        self,
        evidence_ids: tuple[str, ...],
        relation_ids: tuple[str, ...],
        proof_path_ids: tuple[str, ...],
    ) -> ReferenceClosure:
        evidence = set(evidence_ids)
        relations = set(relation_ids)
        proofs = set(proof_path_ids)
        requested = evidence | relations | proofs
        missing: set[str] = set()
        for proof_id in tuple(sorted(proofs)):
            proof = self._proofs.get(proof_id)
            if proof is None:
                missing.add(proof_id)
                continue
            relations.update(proof.relation_ids)
            requested.update(proof.relation_ids)
        truncated = False
        for relation_id in tuple(sorted(relations)):
            if len(evidence) + len(relations) + len(proofs) > self._max_references:
                truncated = True
                break
            relation = self._relations.get(relation_id)
            if relation is None:
                missing.add(relation_id)
                continue
            evidence.update(relation.evidence_ids)
            requested.update(relation.evidence_ids)
            for entity_id in (relation.source_id, relation.target_id):
                requested.add(entity_id)
                entity = self._entities.get(entity_id)
                if entity is None:
                    missing.add(entity_id)
                    continue
                source_evidence_id = entity.properties.get("sourceEvidenceId")
                if isinstance(source_evidence_id, str):
                    evidence.add(source_evidence_id)
                    requested.add(source_evidence_id)
        for evidence_id in tuple(sorted(evidence)):
            if evidence_id not in self._evidence:
                missing.add(evidence_id)
        indexes = (self._evidence, self._entities, self._relations, self._proofs)
        conflicting = tuple(
            sorted(reference_id for reference_id in requested if sum(reference_id in index for index in indexes) > 1)
        )
        return ReferenceClosure(
            tuple(sorted(value for value in evidence if value in self._evidence)),
            tuple(sorted(value for value in relations if value in self._relations)),
            tuple(sorted(value for value in proofs if value in self._proofs)),
            tuple(sorted(missing)),
            conflicting,
            truncated,
        )


def resolve_symbol(
    primary: Evidence,
    knowledge_entries: tuple[object, ...],
    relations: tuple[Relation, ...],
    entities: Mapping[str, Entity],
) -> str | None:
    if isinstance(primary.value, str) and primary.kind in {
        "call_expression",
        "type_reference",
        "macro_replacement_token",
        "macro_expansion",
        "compiler_argument",
        "build_argument",
        "include",
    }:
        return primary.value
    knowledge_values = sorted(
        {
            item.canonical_value
            for item in knowledge_entries
            if isinstance(getattr(item, "canonical_value", None), str)
        }
    )
    if knowledge_values:
        return knowledge_values[0]
    terminal_names = sorted(
        {
            entity.name
            for relation in relations
            for entity_id in (relation.target_id,)
            if (entity := entities.get(entity_id)) is not None and entity.kind == "symbol"
        }
    )
    return terminal_names[0] if terminal_names else None
