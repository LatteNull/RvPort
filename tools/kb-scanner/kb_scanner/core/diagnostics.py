from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from .location import SourceLocation
from .metadata import JsonValue, freeze_metadata


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    stage: str
    severity: DiagnosticSeverity
    message: str
    location: SourceLocation | None = None
    producer: str | None = None
    details: Mapping[str, JsonValue] | None = None
    affects_exit_code: bool = False

    def __post_init__(self) -> None:
        if not all((self.code, self.stage, self.message)):
            raise ValueError("diagnostic code, stage and message must not be empty")
        object.__setattr__(self, "details", freeze_metadata(self.details))

    @property
    def identity(self) -> tuple[object, ...]:
        location = None
        if self.location is not None:
            location = (self.location.path, self.location.line, self.location.column)
        return self.code, self.stage, self.severity.value, self.message, location, self.producer


def merge_diagnostics(*groups: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    merged: list[Diagnostic] = []
    seen: set[tuple[object, ...]] = set()
    for group in groups:
        for diagnostic in group:
            if diagnostic.identity in seen:
                continue
            seen.add(diagnostic.identity)
            merged.append(diagnostic)
    return tuple(merged)
