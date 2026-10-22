"""Scanner-owned occurrence records and macro reference provenance."""
from __future__ import annotations
from dataclasses import replace
import re

from ..vocabulary import BuildRecord
from .conditions import status
from .macros import ARCH_MACROS, PROFILE, MacroEnv, Value


class Records:
    def __init__(self, path: str):
        self.path = path
        self.items: list[BuildRecord] = []
        self.diagnostics: list[str] = []

    def emit(self, kind: str, value: str, line: int, column: int, *, active: bool | None = True,
             parents: tuple[str, ...] = (), package: str = "main", section: str = "preamble", **details) -> str:
        key = f"{self.path}:{line}:{column}:{kind}:{len(self.items)}"
        rpm = {"key": key, "parents": tuple(dict.fromkeys(parents)), "package": package,
               "profile": PROFILE, **details}
        metadata = {"selectionStatus": status(active), "section": section, "rpm": rpm,
                    "reason": str(details.get("reason", "")), "role": "unknown"}
        value = value or "<empty>"
        self.items.append(BuildRecord(kind, value, line, max(1,column), max(1,column) + len(value), metadata,
                                      "medium" if active is None else "high"))
        return key

    def expand(self, env: MacroEnv, raw: str, line: int, column: int, **context) -> Value:
        result = env.expand(raw)
        refs = list(result.refs)
        # Each literal reference keeps its own occurrence; nested names remain in semantic metadata.
        for match in re.finditer(r"(?<!%)%(?:\{[^{}]*\}|\([^()]*\))", raw):
            part = env.expand(match.group())
            prefix = raw[:match.start()]
            row = line + prefix.count('\n')
            col = column + match.start() if '\n' not in prefix else len(prefix.rsplit('\n',1)[1]) + 1
            key = self.emit("build_arch_probe" if set(part.names) & (ARCH_MACROS | {"uname -m"}) else "build_assignment",
                            match.group().splitlines()[0], row, col, **{
                                **context, "parents": (*context.get("parents", ()), *part.refs),
                            }, macroNames=part.names, resolvedValue=part.text, valueKnown=part.text is not None,
                            architectureRelated=bool(set(part.names) & (ARCH_MACROS | {"uname -m"})), reason=part.reason)
            refs.append(key)
        return replace(result, refs=tuple(dict.fromkeys(refs)))

    def unknown(self, raw: str, line: int, reason: str, **context) -> str:
        self.diagnostics.append(f"{self.path}:{line}: {reason} unsupported/unknown")
        return self.emit("build_unsupported", raw.strip() or reason, line, 1,
                         **{**context, "active": None}, reason=reason)

    def damage(self, start: int, reason: str) -> None:
        for index in range(start, len(self.items)):
            item = self.items[index]
            rpm = {**item.metadata["rpm"], "reason": reason, "structureComplete": False}
            self.items[index] = replace(item, metadata={**item.metadata, "rpm": rpm,
                                                       "selectionStatus": "unknown", "reason": reason})
