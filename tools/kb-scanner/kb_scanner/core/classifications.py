from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .evidence import _validate_id, _validate_ids
from .metadata import JsonValue, freeze_metadata


IMPACT_CLASSES = frozenset(
    {"blocking_issue", "actionable_non_blocking", "guarded_inactive", "hint", "unknown"}
)


@dataclass(frozen=True, slots=True)
class Classification:
    """A stable, non-destructive interpretation of one semantic observation root."""

    id: str
    policy_id: str
    impact: str
    reason: str
    observation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    proof_path_ids: tuple[str, ...] = ()
    confidence: str = "unknown"
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id)
        if not all((self.policy_id, self.reason, self.confidence)):
            raise ValueError("classification identity, reason and confidence must not be empty")
        if self.impact not in IMPACT_CLASSES:
            raise ValueError(f"unsupported classification impact: {self.impact}")
        for field in ("observation_ids", "evidence_ids", "knowledge_ids", "relation_ids", "proof_path_ids"):
            values = tuple(sorted(set(getattr(self, field))))
            _validate_ids(values, field.removesuffix("s"))
            object.__setattr__(self, field, values)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
