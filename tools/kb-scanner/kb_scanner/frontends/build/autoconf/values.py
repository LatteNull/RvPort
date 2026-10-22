"""Small shell value domain. None is unknown, never the empty string."""
from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import re

from .syntax import Node, Source


@dataclass(frozen=True, slots=True)
class Value:
    text: str | None
    reason: str = ""


UNKNOWN = Value(None, "autoconf-value-unknown")


def value(source: Source, node: Node | None, env: dict[str, Value], substitute=None) -> Value:
    if node is None:
        return Value("")
    raw = source.text(node)
    if node.kind in {"word", "number", "string_content", "variable_name", "extglob_pattern"}:
        return UNKNOWN if "\\" in raw or "\x00" in raw else Value(raw)
    if node.kind == "raw_string":
        return Value(raw[1:-1])
    if node.kind == "simple_expansion":
        return env.get(raw[1:], UNKNOWN)
    if node.kind == "expansion":
        match = re.fullmatch(r"\$\{([\w]+)(?:(%%|%|##|#)([^{}$`\\]*))?\}", raw)
        if not match:
            return UNKNOWN
        original = env.get(match[1], UNKNOWN)
        if original.text is None or not match[2]:
            return original
        return Value(trim(original.text, match[2], match[3]))
    if node.kind == "command_substitution":
        return substitute(node) if substitute is not None else UNKNOWN
    if node.kind in {"string", "concatenation", "command_name"}:
        parts = [value(source, child, env, substitute) for _, child in node.children
                 if child.kind not in {'"', "'"}]
        if any(part.text is None for part in parts):
            return next(part for part in parts if part.text is None)
        return Value("".join(part.text for part in parts))
    return UNKNOWN


def trim(text: str, operator: str, pattern: str) -> str:
    sizes = range(len(text) + 1)
    if len(operator) == 2:
        sizes = reversed(sizes)
    for size in sizes:
        prefix = operator.startswith("#")
        part = text[:size] if prefix else text[len(text) - size:]
        if fnmatch.fnmatchcase(part, pattern):
            return text[size:] if prefix else text[:len(text) - size]
    return text


def pattern_match(text: str | None, pattern: str | None) -> bool | None:
    if pattern is None or re.search(r"[!+@?*]\(|\\|\[[:.]", pattern):
        return None
    if pattern == "*":
        return True
    return None if text is None else fnmatch.fnmatchcase(text, pattern)


def triplet(text: str | None, target: str) -> bool:
    return bool(text and re.fullmatch(re.escape(target) + r"-[A-Za-z0-9_.]+-[A-Za-z0-9_.+-]+", text))
