from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from ...core import SourceLocation, SourceSpan, normalize_project_path


@dataclass(frozen=True, slots=True)
class SourceByteIndex:
    """Map parser byte offsets to the scanner's 1-based source locations."""

    path: str
    source_length: int
    line_starts: tuple[int, ...]

    @classmethod
    def build(cls, path: str, source: bytes) -> SourceByteIndex:
        if not isinstance(source, bytes):
            raise TypeError("source must be bytes")
        starts = (0, *(index + 1 for index, value in enumerate(source) if value == 0x0A))
        return cls(normalize_project_path(path), len(source), starts)

    def location(self, offset: int) -> SourceLocation:
        return SourceLocation(self.path, *self.coordinates(offset))

    def coordinates(self, offset: int) -> tuple[int, int]:
        """内部标量记录只需行列；公开 SourceLocation 仍保留完整路径校验。"""
        self._validate_offset(offset)
        line_index = bisect_right(self.line_starts, offset) - 1
        return line_index + 1, offset - self.line_starts[line_index] + 1

    def coordinate_span(self, start: int, end: int) -> tuple[int, int, int, int]:
        first, last = self.coordinates(start), self.coordinates(end)
        if end < start:
            raise ValueError("source byte range end must not precede start")
        return (*first, *last)

    def span(self, start: int, end: int) -> SourceSpan:
        self._validate_offset(start)
        self._validate_offset(end)
        if end < start:
            raise ValueError("source byte range end must not precede start")
        return SourceSpan(self.location(start), self.location(end))

    def _validate_offset(self, offset: int) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("source byte offset must be an integer")
        if offset < 0 or offset > self.source_length:
            raise ValueError("source byte offset is outside the source")
