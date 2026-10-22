from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .location import SourceSpan
from .metadata import JsonValue, freeze_json, freeze_metadata


_STABLE_ID = re.compile(r"^[0-9a-f]{64}$")


def _validate_id(value: str, field_name: str = "id") -> None:
    if not _STABLE_ID.fullmatch(value):
        raise ValueError(f"{field_name} must be a complete lowercase SHA-256")


def _validate_ids(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _validate_id(value, field_name)


@dataclass(frozen=True, slots=True)
class Entity:
    id: str
    kind: str
    name: str
    location: SourceSpan | None = None
    properties: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not self.kind or not self.name:
            raise ValueError("entity kind and name must not be empty")
        object.__setattr__(self, "properties", freeze_metadata(self.properties))


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    kind: str
    subject_id: str
    value: JsonValue
    producer: str
    parse_mode: str
    confidence: str
    location: SourceSpan | None = None
    knowledge_sources: tuple[str, ...] = ()
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        _validate_id(self.subject_id, "subject_id")
        if not all((self.kind, self.producer, self.parse_mode, self.confidence)):
            raise ValueError("evidence kind, producer, parse_mode and confidence must not be empty")
        object.__setattr__(self, "value", freeze_json(self.value, field_name="value"))
        object.__setattr__(self, "knowledge_sources", tuple(self.knowledge_sources))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    kind: str
    source_id: str
    target_id: str
    evidence_ids: tuple[str, ...] = ()
    confidence: str = "unknown"
    status: str = "unknown"
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        _validate_id(self.source_id, "source_id")
        _validate_id(self.target_id, "target_id")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        _validate_ids(self.evidence_ids, "evidence_id")
        if not all((self.kind, self.confidence, self.status)):
            raise ValueError("relation kind, confidence and status must not be empty")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
