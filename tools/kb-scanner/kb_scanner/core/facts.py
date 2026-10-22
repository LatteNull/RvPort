from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .evidence import _validate_id, _validate_ids
from .metadata import JsonValue, freeze_metadata


def _unique_sorted(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True, slots=True)
class NormalizedFact:
    id: str
    kind: str
    subject_id: str
    canonical_value: str
    scope: str
    evidence_ids: tuple[str, ...]
    context_ids: tuple[str, ...] = ()
    producers: tuple[str, ...] = ()
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        _validate_id(self.subject_id, "subject_id")
        if not all((self.kind, self.canonical_value, self.scope)):
            raise ValueError("normalized fact fields must not be empty")
        evidence_ids = _unique_sorted(tuple(self.evidence_ids))
        if not evidence_ids:
            raise ValueError("normalized fact requires at least one evidence reference")
        context_ids = _unique_sorted(tuple(self.context_ids))
        _validate_ids(evidence_ids, "evidence_id")
        _validate_ids(context_ids, "context_id")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "context_ids", context_ids)
        object.__setattr__(self, "producers", _unique_sorted(tuple(self.producers)))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
