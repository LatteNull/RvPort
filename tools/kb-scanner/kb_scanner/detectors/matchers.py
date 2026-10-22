from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from ..core import KnowledgeEntry, KnowledgeSnapshot, NormalizedFact
from .definitions import DetectorDefinition


_ARCHITECTURE_TOKEN = re.compile(r"(?i)(?<![A-Za-z0-9])(?:x86(?:_64)?|i[3-6]86|sse[0-9.]*|avx(?:2|512)?)(?![A-Za-z0-9])")


@dataclass(frozen=True, slots=True)
class MatchResult:
    knowledge_ids: tuple[str, ...]
    status: str
    basis: str


class KnowledgeIndex:
    __slots__ = ("_by_kind",)

    def __init__(self, snapshot: KnowledgeSnapshot) -> None:
        grouped: dict[str, dict[str, list[KnowledgeEntry]]] = defaultdict(lambda: defaultdict(list))
        for entry in snapshot.entries:
            grouped[entry.fact_kind][entry.canonical_value].append(entry)
        self._by_kind = MappingProxyType(
            {
                kind: MappingProxyType(
                    {
                        value: tuple(sorted(entries, key=lambda item: item.id))
                        for value, entries in sorted(values.items())
                    }
                )
                for kind, values in sorted(grouped.items())
            }
        )

    @property
    def by_kind(self) -> Mapping[str, Mapping[str, tuple[KnowledgeEntry, ...]]]:
        return self._by_kind


def match_fact(
    definition: DetectorDefinition,
    fact: NormalizedFact,
    index: KnowledgeIndex,
) -> MatchResult | None:
    if fact.kind != definition.input_kind:
        return None
    if definition.matcher == "structural":
        return MatchResult((), definition.status, f"structural:{fact.kind}") if fact.canonical_value else None
    if definition.matcher == "comment_hint":
        return MatchResult((), "hint", "architecture-token-in-comment") if _ARCHITECTURE_TOKEN.search(fact.canonical_value) else None
    if definition.matcher == "architecture_candidate":
        return MatchResult((), "candidate", "architecture-shaped-identifier") if _ARCHITECTURE_TOKEN.search(fact.canonical_value) else None
    if definition.matcher == "enum_architecture_candidate":
        components = _identifier_components(fact.canonical_value)
        terminal_components = _identifier_terminal_components(fact.canonical_value)
        matches: dict[str, KnowledgeEntry] = {}
        for knowledge_kind in definition.knowledge_kinds:
            for value, entries in index.by_kind.get(knowledge_kind, {}).items():
                if value.casefold() in terminal_components:
                    for entry in entries:
                        matches[entry.id] = entry
        matched_values = {entry.canonical_value.casefold() for entry in matches.values()}
        matches = {
            entry_id: entry
            for entry_id, entry in matches.items()
            if not any(
                other != entry.canonical_value.casefold()
                and other.startswith(entry.canonical_value.casefold())
                and other[len(entry.canonical_value) :].isdigit()
                for other in matched_values
            )
        }
        strong = next((value for value in terminal_components if re.fullmatch(r"(?:x86(?:64)?|i[3-6]86|sse\d*|avx(?:2|512)?|aesni)", value)), None)
        if strong is None:
            strong = next((value for value in components if re.fullmatch(r"x86(?:64)?|i[3-6]86", value)), None)
        if not matches and strong is None:
            return None
        basis = "enum-knowledge:" + ",".join(definition.knowledge_kinds) if matches else f"enum-family-token:{strong}"
        return MatchResult(tuple(sorted(matches)), "candidate", basis)

    matches: dict[str, KnowledgeEntry] = {}
    for knowledge_kind in definition.knowledge_kinds:
        values = index.by_kind.get(knowledge_kind, {})
        if definition.matcher == "exact":
            candidates = values.get(fact.canonical_value, ())
        elif definition.matcher == "flag":
            candidates = tuple(
                entry
                for value, entries in values.items()
                if fact.canonical_value == value or fact.canonical_value.startswith(f"{value}=")
                for entry in entries
            )
        else:
            candidates = tuple(
                entry
                for value, entries in values.items()
                if _contains_token(
                    re.sub(r"\s+", "", fact.canonical_value) if knowledge_kind == "vectorWidthMarkers" else fact.canonical_value,
                    re.sub(r"\s+", "", value) if knowledge_kind == "vectorWidthMarkers" else value,
                    case_insensitive=knowledge_kind in {
                        "assemblyInstructions", "registerNames", "targetFeatures", "architectureAliases",
                    },
                )
                for entry in entries
            )
        for entry in candidates:
            matches[entry.id] = entry
    if not matches:
        return None
    return MatchResult(tuple(sorted(matches)), definition.status, f"{definition.matcher}:{','.join(definition.knowledge_kinds)}")


def _contains_token(text: str, token: str, *, case_insensitive: bool = False) -> bool:
    if text == token:
        return True
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, re.IGNORECASE if case_insensitive else 0) is not None


def _identifier_components(value: str) -> frozenset[str]:
    pieces: set[str] = set()
    for segment in re.split(r"::|[^A-Za-z0-9]+", value):
        if not segment:
            continue
        words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", segment)
        lowered = [word.casefold() for word in words]
        pieces.add(segment.casefold())
        pieces.update(lowered)
        pieces.update(left + right for left, right in zip(lowered, lowered[1:]) if left.isalpha() and right.isdigit())
    return frozenset(pieces)


def _identifier_terminal_components(value: str) -> frozenset[str]:
    member = value.split("::")[-1]
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+", member)
    lowered = [word.casefold() for word in words]
    result = {member.casefold()}
    if lowered:
        result.add(lowered[-1])
    if len(lowered) >= 2 and lowered[-2].isalpha() and lowered[-1].isdigit():
        result.add(lowered[-2] + lowered[-1])
    return frozenset(result)
