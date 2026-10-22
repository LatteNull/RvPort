from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ...core import (
    AnalysisSnapshot, Assessment, AssessmentSnapshot, Classification, ClassificationSnapshot,
    Evidence, FrontendSnapshot, KnowledgeEntry, KnowledgeSnapshot, NormalizedSnapshot,
    Observation, ProofPath, Relation,
)


def _unique(items) -> Mapping[str, object]:
    values: dict[str, object] = {}
    for item in items:
        if item.id in values and values[item.id] != item:
            raise ValueError(f"conflicting snapshot id: {item.id}")
        values[item.id] = item
    return MappingProxyType(values)


@dataclass(frozen=True, slots=True)
class SnapshotIndex:
    evidence: Mapping[str, Evidence]
    knowledge: Mapping[str, KnowledgeEntry]
    relations: Mapping[str, Relation]
    proofs: Mapping[str, ProofPath]
    observations: Mapping[str, Observation]
    classifications: Mapping[str, Classification]
    assessments: Mapping[str, Assessment]
    entities: Mapping[str, object] = field(default_factory=dict)
    facts: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def build(cls, knowledge, frontend, facts, analysis, detections, classifications, assessments):
        del detections
        return cls(
            _unique((*frontend.evidence, *facts.evidence)), _unique(knowledge.entries),
            _unique(analysis.relations), _unique(analysis.proof_paths),
            _unique(classifications.observations), _unique(classifications.classifications),
            _unique(assessments.assessments),
            _unique(analysis.entities),
            _unique(facts.facts),
        )
