from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from .identity import canonicalize_fact_value, curated_entry_id
from .schema import CuratedFactsModel, GeneratedFactsV2Model, ReferenceRegistryModel


DecisionStatus = Literal["generated", "accepted", "rejected", "deferred"]


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    candidate_id: str
    category: str
    canonical_value: str
    status: DecisionStatus
    reference_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if not all((self.candidate_id, self.category, self.canonical_value, self.rationale)):
            raise ValueError("candidate decision fields must not be empty")
        if self.status not in {"generated", "accepted", "rejected", "deferred"}:
            raise ValueError("unknown candidate decision status")
        if self.status in {"generated", "accepted"} and not self.reference_ids:
            raise ValueError("runtime decisions require authoritative references")
        object.__setattr__(self, "reference_ids", tuple(sorted(set(self.reference_ids))))


def render_model(model: BaseModel) -> bytes:
    payload = model.model_dump(mode="json", exclude_none=True)
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def lint_generated(model: GeneratedFactsV2Model) -> tuple[str, ...]:
    keys = [(item.factKind, item.architectureFamily, item.canonicalValue) for item in model.facts]
    failures: list[str] = []
    if keys != sorted(keys):
        failures.append("facts-not-sorted")
    for item in model.facts:
        if canonicalize_fact_value(item.factKind, item.canonicalValue) != item.canonicalValue:
            failures.append(f"non-canonical:{item.factKind}:{item.canonicalValue}")
    return tuple(failures)


def lint_curated(model: CuratedFactsModel, registry: ReferenceRegistryModel) -> tuple[str, ...]:
    reference_ids = {item.referenceId for item in registry.references}
    failures: list[str] = []
    keys = [(item.factKind, item.architectureFamily, item.canonicalValue) for item in model.entries]
    if keys != sorted(keys):
        failures.append("entries-not-sorted")
    for item in model.entries:
        if item.entryId != curated_entry_id(item.factKind, item.architectureFamily, item.canonicalValue):
            failures.append(f"entry-id-mismatch:{item.entryId}")
        missing = sorted(set(item.referenceIds) - reference_ids)
        if missing:
            failures.append(f"missing-references:{item.entryId}:{','.join(missing)}")
    return tuple(failures)


def runtime_decisions(decisions: Iterable[CandidateDecision]) -> tuple[CandidateDecision, ...]:
    return tuple(sorted((item for item in decisions if item.status == "accepted"), key=lambda item: item.candidate_id))
