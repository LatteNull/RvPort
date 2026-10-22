from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .evidence import _validate_id, _validate_ids
from .metadata import JsonValue, freeze_metadata


@dataclass(frozen=True, slots=True)
class Observation:
    id: str
    detector_id: str
    kind: str
    evidence_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    confidence: str = "unknown"
    status: str = "candidate"
    metadata: Mapping[str, JsonValue] | None = None
    knowledge_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not all((self.detector_id, self.kind, self.confidence, self.status)):
            raise ValueError("observation fields must not be empty")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "relation_ids", tuple(self.relation_ids))
        object.__setattr__(self, "knowledge_ids", tuple(sorted(set(self.knowledge_ids))))
        _validate_ids(self.evidence_ids, "evidence_id")
        _validate_ids(self.relation_ids, "relation_id")
        _validate_ids(self.knowledge_ids, "knowledge_id")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class Assessment:
    id: str
    kind: str
    state: str
    evidence_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    confidence: str = "unknown"
    metadata: Mapping[str, JsonValue] | None = None
    classification_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    proof_path_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not all((self.kind, self.state, self.confidence)):
            raise ValueError("assessment kind, state and confidence must not be empty")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "relation_ids", tuple(self.relation_ids))
        object.__setattr__(self, "classification_ids", tuple(sorted(set(self.classification_ids))))
        object.__setattr__(self, "observation_ids", tuple(sorted(set(self.observation_ids))))
        object.__setattr__(self, "proof_path_ids", tuple(sorted(set(self.proof_path_ids))))
        _validate_ids(self.evidence_ids, "evidence_id")
        _validate_ids(self.relation_ids, "relation_id")
        _validate_ids(self.classification_ids, "classification_id")
        _validate_ids(self.observation_ids, "observation_id")
        _validate_ids(self.proof_path_ids, "proof_path_id")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
