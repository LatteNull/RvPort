from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...core import Entity, Evidence, SourceSpan, stable_id


IDENTITY_VERSION = 1
CPP_EVIDENCE_KINDS = frozenset(
    {
        "usage_scope",
        "preprocessor_condition",
        "preprocessor_branch",
        "include",
        "macro_definition",
        "macro_expansion",
        "macro_parameter",
        "macro_argument_token",
        "macro_replacement_token",
        "call_expression",
        "type_reference",
        "template_declaration",
        "constexpr_condition",
        "selection_condition",
        "enum_declaration",
        "enum_member_declaration",
        "enum_member_reference",
        "inline_asm",
        "declaration_attribute",
        "function_declaration",
        "function_semantics",
        "comment",
    }
)


def make_source_file_entity(relative_path: str, languages: Sequence[str], scanner_version: str) -> Entity:
    normalized_languages = tuple(sorted(set(languages)))
    return Entity(
        id=stable_id("source_file", IDENTITY_VERSION, relative_path, normalized_languages, scanner_version),
        kind="source_file",
        name=relative_path,
        properties={
            "identityVersion": IDENTITY_VERSION,
            "languageCandidates": normalized_languages,
        },
    )


def make_evidence(
    *,
    kind: str,
    subject_id: str,
    value: Any,
    producer: str,
    parse_mode: str,
    confidence: str,
    span: SourceSpan,
    metadata: Mapping[str, Any] | None = None,
    context_id: str | None = None,
) -> Evidence:
    if kind not in CPP_EVIDENCE_KINDS:
        raise ValueError(f"unsupported C/C++ evidence kind: {kind}")
    details = dict(metadata or {})
    details["identityVersion"] = IDENTITY_VERSION
    if context_id is not None:
        details["compilationContextId"] = context_id
    return Evidence(
        id=stable_id(
            "evidence",
            IDENTITY_VERSION,
            kind,
            subject_id,
            value,
            span,
            producer,
            parse_mode,
            context_id,
        ),
        kind=kind,
        subject_id=subject_id,
        value=value,
        producer=producer,
        parse_mode=parse_mode,
        confidence=confidence,
        location=span,
        metadata=details,
    )


def entity_sort_key(entity: Entity) -> tuple[str, str, str]:
    return entity.kind, entity.name, entity.id


def evidence_sort_key(evidence: Evidence) -> tuple[object, ...]:
    if evidence.location is None:
        location: tuple[object, ...] = ("", 0, 0, 0, 0)
    else:
        location = (
            evidence.location.start.path,
            evidence.location.start.line,
            evidence.location.start.column or 0,
            evidence.location.end.line,
            evidence.location.end.column or 0,
        )
    context_id = str(evidence.metadata.get("compilationContextId", ""))
    kind_order = {
        "enum_declaration": 0,
        "enum_member_declaration": 1,
        "constexpr_condition": 2,
        "selection_condition": 2,
        "enum_member_reference": 3,
    }
    return (*location, kind_order.get(evidence.kind, 10), evidence.kind, evidence.producer, context_id, evidence.id)
