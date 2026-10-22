from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .evidence import _validate_id, _validate_ids
from .metadata import JsonValue, freeze_metadata


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _unique_sorted(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    id: str
    source_id: str
    kind: str
    logical_path: str
    sha256: str
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not all((self.source_id, self.kind, self.logical_path)):
            raise ValueError("knowledge source identity fields must not be empty")
        if self.logical_path.startswith(("/", "\\")) or ".." in self.logical_path.replace("\\", "/").split("/"):
            raise ValueError("knowledge source path must be project relative")
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("knowledge source sha256 must be a complete lowercase digest")
        object.__setattr__(self, "logical_path", self.logical_path.replace("\\", "/"))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class KnowledgeEntry:
    id: str
    fact_kind: str
    architecture_family: str
    canonical_value: str
    source_ids: tuple[str, ...]
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not all((self.fact_kind, self.architecture_family, self.canonical_value)):
            raise ValueError("knowledge entry fields must not be empty")
        source_ids = _unique_sorted(tuple(self.source_ids))
        if not source_ids:
            raise ValueError("knowledge entry requires at least one source")
        _validate_ids(source_ids, "source_id")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
