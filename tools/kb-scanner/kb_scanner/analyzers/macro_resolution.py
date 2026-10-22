from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from ..core import Entity, Evidence


@dataclass(frozen=True, slots=True)
class MacroResolution:
    definitions: tuple[Entity, ...]
    status: str
    reason: str | None = None


class MacroDefinitionResolver:
    __slots__ = ("_definition_file", "_evidence")

    def __init__(self, definition_file: Mapping[str, str], evidence: Mapping[str, Evidence]) -> None:
        self._definition_file = definition_file
        self._evidence = evidence

    def resolve(
        self,
        invocation: Evidence,
        candidates: tuple[Entity, ...],
        visible_files: set[str],
    ) -> MacroResolution:
        considered = tuple(item for item in candidates if self._definition_file.get(item.id) in visible_files)
        invocation_configuration = _configuration(invocation)
        if invocation_configuration:
            matching = tuple(
                item
                for item in considered
                if (definition := self._definition_evidence(item)) is not None
                and _configuration(definition) in {None, invocation_configuration}
            )
            if matching:
                considered = matching
        invocation_order = _order(invocation)
        if invocation_order is not None:
            considered = tuple(
                item
                for item in considered
                if (definition := self._definition_evidence(item)) is not None
                and (_order(definition) is None or _order(definition) <= invocation_order)
            )
        same_file = tuple(
            item
            for item in considered
            if self._definition_file.get(item.id) == invocation.subject_id
            and (definition := self._definition_evidence(item)) is not None
            and definition.location is not None
            and invocation.location is not None
            and (
                definition.location.start.line,
                definition.location.start.column or 0,
            ) <= (
                invocation.location.start.line,
                invocation.location.start.column or 0,
            )
        )
        if same_file:
            latest = max(
                (
                    self._definition_evidence(item).location.start.line,
                    self._definition_evidence(item).location.start.column or 0,
                )
                for item in same_file
            )
            considered = tuple(
                item
                for item in same_file
                if (
                    self._definition_evidence(item).location.start.line,
                    self._definition_evidence(item).location.start.column or 0,
                ) == latest
            )
        considered = tuple(sorted(considered, key=lambda item: item.id))
        if not considered:
            return MacroResolution((), "unknown", "unresolved-macro")
        if len(considered) == 1 or _equivalent(considered, self._evidence):
            return MacroResolution(considered, "complete")
        return MacroResolution(considered, "partial", "ambiguous-macro-definition")

    def _definition_evidence(self, entity: Entity) -> Evidence | None:
        evidence_id = entity.properties.get("sourceEvidenceId")
        return self._evidence.get(evidence_id) if isinstance(evidence_id, str) else None


def _configuration(evidence: Evidence) -> str | None:
    value = evidence.metadata.get("compilationContextId") or evidence.metadata.get("configuration")
    return value if isinstance(value, str) and value else None


def _order(evidence: Evidence) -> int | None:
    value = evidence.metadata.get("includeOrder") or evidence.metadata.get("definitionOrder")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _equivalent(definitions: tuple[Entity, ...], evidence: Mapping[str, Evidence]) -> bool:
    signatures = set()
    for definition in definitions:
        evidence_id = definition.properties.get("sourceEvidenceId")
        item = evidence.get(evidence_id) if isinstance(evidence_id, str) else None
        if item is None:
            return False
        metadata = {
            key: value
            for key, value in item.metadata.items()
            if key not in {"compilationContextId", "sourcePath", "sourceFileId"}
        }
        signatures.add((str(item.value), repr(sorted(metadata.items()))))
    return len(signatures) == 1
