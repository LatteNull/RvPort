from __future__ import annotations

from dataclasses import dataclass

from .evidence import _validate_id, _validate_ids


PROOF_STATUSES = frozenset({"complete", "partial", "unknown"})
SEARCH_STATUSES = frozenset({"complete", "partial", "unknown", "not_found"})


@dataclass(frozen=True, slots=True)
class ProofPath:
    id: str
    source_id: str
    target_id: str
    relation_ids: tuple[str, ...] = ()
    status: str = "unknown"
    reason: str | None = None
    visited: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        _validate_id(self.id)
        _validate_id(self.source_id, "source_id")
        _validate_id(self.target_id, "target_id")
        relation_ids = tuple(self.relation_ids)
        _validate_ids(relation_ids, "relation_id")
        if self.status not in PROOF_STATUSES:
            raise ValueError(f"unsupported proof status: {self.status}")
        if self.visited < 0:
            raise ValueError("visited must not be negative")
        if self.status == "complete" and self.truncated:
            raise ValueError("a complete proof path cannot be truncated")
        if self.reason is not None and not self.reason:
            raise ValueError("proof reason must not be empty")
        object.__setattr__(self, "relation_ids", relation_ids)


@dataclass(frozen=True, slots=True)
class PathSearchResult:
    paths: tuple[tuple[str, ...], ...] = ()
    status: str = "not_found"
    visited: int = 0
    truncated: bool = False
    reason: str | None = None

    def __post_init__(self) -> None:
        paths = tuple(tuple(path) for path in self.paths)
        for path in paths:
            _validate_ids(path, "relation_id")
        if self.status not in SEARCH_STATUSES:
            raise ValueError(f"unsupported path search status: {self.status}")
        if self.visited < 0:
            raise ValueError("visited must not be negative")
        if self.status == "complete" and self.truncated:
            raise ValueError("a complete path search cannot be truncated")
        if self.reason is not None and not self.reason:
            raise ValueError("path search reason must not be empty")
        if self.status == "not_found" and paths:
            raise ValueError("not_found path search cannot contain paths")
        object.__setattr__(self, "paths", paths)
