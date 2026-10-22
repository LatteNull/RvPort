from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Generic, TypeVar

from .diagnostics import Diagnostic
from .evidence import Entity, Evidence, Relation
from .facts import NormalizedFact
from .knowledge import KnowledgeEntry, KnowledgeSource
from .classifications import Classification
from .observations import Assessment, Observation
from .paths import ProofPath


T = TypeVar("T")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CompletionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StageResult(Generic[T]):
    value: T | None
    status: CompletionStatus = CompletionStatus.COMPLETE
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.status in {CompletionStatus.COMPLETE, CompletionStatus.PARTIAL} and self.value is None:
            raise ValueError("complete and partial stage results require a value")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    name: str
    path: Path
    sha256: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("artifact name must not be empty")
        object.__setattr__(self, "path", self.path.resolve())
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be a complete lowercase digest")


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    root: Path
    files: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())
        object.__setattr__(self, "files", tuple(self.files))


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    identity: str
    version: str
    sources: tuple[KnowledgeSource, ...] = ()
    entries: tuple[KnowledgeEntry, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "entries", tuple(self.entries))


@dataclass(frozen=True, slots=True)
class FrontendSnapshot:
    entities: tuple[Entity, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class NormalizedSnapshot:
    entities: tuple[Entity, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    facts: tuple[NormalizedFact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "facts", tuple(self.facts))


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    relations: tuple[Relation, ...] = ()
    entities: tuple[Entity, ...] = ()
    proof_paths: tuple[ProofPath, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "proof_paths", tuple(self.proof_paths))


@dataclass(frozen=True, slots=True)
class DetectionSnapshot:
    observations: tuple[Observation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))


@dataclass(frozen=True, slots=True)
class ClassificationSnapshot:
    observations: tuple[Observation, ...] = ()
    classifications: tuple[Classification, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "classifications", tuple(self.classifications))


@dataclass(frozen=True, slots=True)
class AssessmentSnapshot:
    assessments: tuple[Assessment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessments", tuple(self.assessments))


@dataclass(frozen=True, slots=True)
class PipelineResult:
    success: bool
    exit_code: int
    status: CompletionStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if self.exit_code < 0:
            raise ValueError("exit_code must not be negative")
        if self.success != (self.exit_code == 0):
            raise ValueError("success must match exit_code")
