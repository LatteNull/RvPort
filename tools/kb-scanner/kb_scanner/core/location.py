from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


def normalize_project_path(path: str | Path, project_root: Path | None = None) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        if project_root is None:
            raise ValueError("absolute source paths require a project root")
        root = project_root.resolve()
        resolved = candidate.resolve()
        try:
            candidate = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("source path must be inside the project root") from exc

    raw = str(candidate).replace("\\", "/")
    normalized = PurePosixPath(raw)
    parts = tuple(part for part in normalized.parts if part not in {"", "."})
    if not parts or any(part == ".." for part in parts) or normalized.is_absolute():
        raise ValueError("source path must be a non-empty project-relative path")
    return PurePosixPath(*parts).as_posix()


@dataclass(frozen=True, slots=True)
class SourceLocation:
    path: str
    line: int
    column: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalize_project_path(self.path))
        if self.line < 1:
            raise ValueError("line must be at least 1")
        if self.column is not None and self.column < 1:
            raise ValueError("column must be at least 1")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: SourceLocation
    end: SourceLocation

    def __post_init__(self) -> None:
        if self.start.path != self.end.path:
            raise ValueError("source span endpoints must use the same path")
        start_position = (self.start.line, self.start.column or 1)
        end_position = (self.end.line, self.end.column or 1)
        if end_position < start_position:
            raise ValueError("source span end must not precede its start")
