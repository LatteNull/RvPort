from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ...core import Entity, Evidence, SourceLocation, SourceSpan, normalize_project_path, stable_id


IDENTITY_VERSION = 1


class BuildInputKind(str, Enum):
    MAKE = "make"
    SHELL = "shell"
    M4 = "m4"
    CMAKE = "cmake"
    CMAKE_SOURCE = "cmake-source"
    MESON = "meson"
    CTEST = "ctest"
    COMPILATION_DATABASE = "compilation-database"
    RPM = "rpm"


class SelectionStatus(str, Enum):
    SELECTED = "selected"
    INACTIVE = "inactive"
    NOT_SELECTED = "not_selected"
    UNKNOWN = "unknown"


BUILD_EVIDENCE_KINDS = frozenset(
    {
        "build_assignment",
        "build_condition",
        "build_branch",
        "build_include",
        "build_target",
        "build_source",
        "build_directory",
        "build_argument",
        "build_dependency",
        "build_artifact",
        "build_arch_probe",
        "build_configuration",
        "build_package_section",
        "build_arch_constraint",
        "build_unsupported",
    }
)


@dataclass(frozen=True, slots=True)
class BuildRecord:
    kind: str
    value: str
    line: int
    start_column: int
    end_column: int
    metadata: Mapping[str, Any] | None = None
    confidence: str = "high"

    def __post_init__(self) -> None:
        if self.kind not in BUILD_EVIDENCE_KINDS:
            raise ValueError(f"unsupported build evidence kind: {self.kind}")
        if not self.value:
            raise ValueError("build record value must not be empty")
        if self.line < 1 or self.start_column < 1 or self.end_column < self.start_column:
            raise ValueError("invalid build record location")
        if self.confidence not in {"high", "medium", "low"}:
            raise ValueError("unsupported build record confidence")


def make_build_file_entity(relative_path: str, input_kind: BuildInputKind, scanner_version: str) -> Entity:
    path = normalize_project_path(relative_path)
    return Entity(
        id=stable_id("build_file", IDENTITY_VERSION, path, input_kind.value, scanner_version),
        kind="build_file",
        name=path,
        properties={"identityVersion": IDENTITY_VERSION, "inputKind": input_kind.value},
    )


def make_build_evidence(
    record: BuildRecord,
    *,
    path: str,
    subject_id: str,
    producer: str,
    input_kind: BuildInputKind,
) -> Evidence:
    normalized_path = normalize_project_path(path)
    span = SourceSpan(
        SourceLocation(normalized_path, record.line, record.start_column),
        SourceLocation(normalized_path, (record.metadata or {}).get("endLine", record.line),
                       (record.metadata or {}).get("endColumn", record.end_column)),
    )
    metadata = dict(record.metadata or {})
    metadata.update({"identityVersion": IDENTITY_VERSION, "inputKind": input_kind.value})
    return Evidence(
        id=stable_id(
            "build_evidence",
            IDENTITY_VERSION,
            record.kind,
            subject_id,
            record.value,
            span,
            producer,
            metadata,
        ),
        kind=record.kind,
        subject_id=subject_id,
        value=record.value,
        producer=producer,
        parse_mode="static-build",
        confidence=record.confidence,
        location=span,
        metadata=metadata,
    )


def record_for_token(
    kind: str,
    value: str,
    line: int,
    line_text: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    confidence: str = "high",
) -> BuildRecord:
    index = line_text.find(value)
    start = index + 1 if index >= 0 else 1
    return BuildRecord(kind, value, line, start, start + len(value), metadata, confidence)
