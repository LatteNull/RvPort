from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...core import SourceSpan, normalize_project_path
from .models import ContextBudget, ContextLine, Highlight, Position, Source, SourceContext, Span


class SourceContextProjector:
    def __init__(
        self, root: Path, *, before: int = 20, after: int = 20, max_lines: int = 256,
        max_characters: int = 65536, reader: Callable[[Path], str] | None = None,
    ) -> None:
        self._root = root.resolve()
        if min(before, after) < 0 or min(max_lines, max_characters) < 1:
            raise ValueError("context windows must be nonnegative and budgets positive")
        self._before = before
        self._after = after
        self._max_lines = min(max_lines, 256)
        self._max_characters = min(max_characters, 65536)
        self._reader = reader or (lambda path: path.read_text(encoding="utf-8"))
        self._cache: dict[Path, tuple[str, ...] | Exception] = {}
        self._projections: dict[SourceSpan, Source] = {}
        self._paths: dict[str, Path | None] = {}
        self._relative_paths: dict[str, str] = {}
        self._budgets: dict[bool, ContextBudget] = {}
        self._line_models: dict[tuple[Path, int], ContextLine] = {}

    def project(self, source_span: SourceSpan) -> Source:
        if source_span not in self._projections:
            self._projections[source_span] = self._project(source_span)
        return self._projections[source_span]

    def _project(self, source_span: SourceSpan) -> Source:
        raw_path = source_span.start.path
        if raw_path not in self._relative_paths:
            self._relative_paths[raw_path] = normalize_project_path(raw_path)
        relative = self._relative_paths[raw_path]
        if relative not in self._paths:
            candidate = (self._root / relative).resolve()
            try:
                candidate.relative_to(self._root)
            except ValueError:
                candidate = None
            self._paths[relative] = candidate
        candidate = self._paths[relative]
        span = Span(
            start=Position(line=source_span.start.line, column=source_span.start.column or 1),
            end=Position(line=source_span.end.line, column=source_span.end.column or (source_span.start.column or 1) + 1),
        )
        if candidate is None:
            return Source(file=relative, span=span, context=self._unavailable())
        cached = self._cache.get(candidate)
        if cached is None:
            try:
                cached = tuple(self._reader(candidate).splitlines())
            except (OSError, UnicodeError) as exc:
                cached = exc
            self._cache[candidate] = cached
        if isinstance(cached, Exception):
            return Source(file=relative, span=span, context=self._unavailable())
        lines = cached
        if not lines or source_span.start.line > len(lines):
            return Source(file=relative, span=span, context=self._unavailable())
        first = max(1, source_span.start.line - self._before)
        last = min(len(lines), source_span.end.line + self._after)
        end_line = source_span.end.line - int(source_span.end.column == 1 and source_span.end.line > source_span.start.line)
        hit_last = min(len(lines), end_line)
        # Visit the hit first, then alternate the closest preceding/following
        # lines. Never shorten text: columns always refer to original lines.
        selected = []
        characters = 0
        for number in self._priority_lines(source_span.start.line, hit_last, first, last):
            text = lines[number - 1]
            if len(selected) == self._max_lines:
                break
            if characters + len(text) <= self._max_characters:
                selected.append((number, text))
                characters += len(text)
        selected.sort()
        truncated = len(selected) < last - first + 1
        selected_numbers = {number for number, _ in selected}
        highlights = []
        invalid_highlight = end_line > len(lines)
        for line in sorted(selected_numbers.intersection(range(source_span.start.line, hit_last + 1))):
            text = lines[line - 1]
            start = source_span.start.column or 1 if line == source_span.start.line else 1
            if not text or start > len(text):
                invalid_highlight = True
                continue
            end = source_span.end.column or len(text) + 1 if line == source_span.end.line else len(text) + 1
            end = max(start + 1, min(end, len(text) + 1))
            highlights.append(Highlight(line=line, startColumn=start, endColumn=end))
        status = "partial" if truncated or invalid_highlight or not highlights else "complete"
        reasons = ("context_budget_exceeded",) if truncated else (("context_unavailable",) if invalid_highlight or not highlights else ())
        for number, text in selected:
            key = candidate, number
            if key not in self._line_models:
                self._line_models[key] = ContextLine(line=number, text=text)
        context = SourceContext(
            status=status, reasonCodes=reasons,
            lines=tuple(self._line_models[candidate, number] for number, _ in selected),
            highlights=tuple(highlights),
            budget=self._budget(truncated),
        )
        return Source(file=relative, span=span, context=context)

    @staticmethod
    def _priority_lines(start: int, end: int, first: int, last: int):
        yield from range(start, end + 1)
        for distance in range(1, max(start - first, last - end) + 1):
            if start - distance >= first:
                yield start - distance
            if end + distance <= last:
                yield end + distance

    def _budget(self, truncated: bool) -> ContextBudget:
        if truncated not in self._budgets:
            self._budgets[truncated] = ContextBudget(beforeLines=self._before, afterLines=self._after, maxLines=self._max_lines, maxCharacters=self._max_characters, truncated=truncated)
        return self._budgets[truncated]

    def _unavailable(self) -> SourceContext:
        return SourceContext(status="unavailable", reasonCodes=("context_unavailable",), budget=self._budget(False))
