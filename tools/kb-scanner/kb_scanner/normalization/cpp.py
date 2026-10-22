from __future__ import annotations

from collections import defaultdict

from ..core import (
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    Evidence,
    FrontendSnapshot,
    NormalizedFact,
    NormalizedSnapshot,
    ScanContext,
    StageResult,
    normalize_project_path,
    stable_id,
)
from ..frontends.cpp.compilation_database import compilation_context_id
from ..knowledge.identity import canonicalize_fact_value
from .functions import valid_function, valid_owner, merge_metadata
from .usage import validate_usage, merge_usage


_KIND_MAP = {
    "test_content": "test_content",
    "test_structure": "test_structure",
    "usage_scope": "usage_scope",
    "include": "include",
    "call_expression": "symbol",
    "type_reference": "type",
    "macro_definition": "macro",
    "macro_expansion": "macro",
    "macro_parameter": "macro_parameter",
    "macro_argument_token": "macro_argument",
    "macro_replacement_token": "macro_replacement",
    "preprocessor_condition": "preprocessor",
    "preprocessor_branch": "preprocessor",
    "inline_asm": "inline_asm",
    "comment": "comment",
    "declaration_attribute": "declaration_attribute",
    "function_declaration": "function_declaration",
    "function_semantics": "function_semantics",
    "enum_declaration": "enum_declaration",
    "enum_member_declaration": "enum_member",
    "enum_member_reference": "enum_reference",
    "constexpr_condition": "selection_condition",
    "selection_condition": "selection_condition",
    "template_declaration": "template_declaration",
}


class CppEvidenceNormalizer:
    __slots__ = ()

    def normalize(self, context: ScanContext, frontend: FrontendSnapshot) -> StageResult[NormalizedSnapshot]:
        entity_ids = {item.id for item in frontend.entities}
        evidence = list(frontend.evidence)
        diagnostics: list[Diagnostic] = []
        fatal = False
        for item in frontend.evidence:
            if item.subject_id not in entity_ids:
                diagnostics.append(_diagnostic("normalization.unknown-subject", "Evidence references an unknown subject", error=True))
                fatal = True

        derived, compiler_diagnostics = self._compiler_argument_evidence(context, frontend)
        evidence.extend(derived)
        diagnostics.extend(compiler_diagnostics)
        if fatal:
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=tuple(diagnostics))

        groups: dict[tuple[str, str, str, str], list[Evidence]] = defaultdict(list)
        context_ids: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
        metadata: dict[tuple[str, str, str, str], dict[str, object]] = {}
        attachment_definition_ids: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
        enum_declarations = {value.id for value in evidence if value.kind == "enum_declaration"}
        enum_members = {value.id for value in evidence if value.kind == "enum_member_declaration"}
        definitions = {value.id for value in evidence if value.kind == "macro_definition"}
        functions = {value.id: value for value in evidence if value.kind == "function_declaration"}
        for item in sorted(evidence, key=lambda value: value.id):
            if item.kind == "usage_scope" and (errors := validate_usage(item)):
                diagnostics.append(_diagnostic("normalization.invalid-usage-structure",
                    "用途记录无效，不能用于候选排除 / Invalid usage records cannot support exclusion: " + ",".join(errors)))
                continue
            if item.kind == "function_declaration" and not valid_function(item):
                diagnostics.append(_diagnostic("normalization.invalid-function-structure", "Function source ranges are invalid", error=True))
                fatal = True
                continue
            if not valid_owner(item, functions):
                diagnostics.append(_diagnostic("normalization.invalid-function-owner", "Function owner reference is invalid", error=True))
                fatal = True
                continue
            if item.kind in {"macro_parameter", "macro_replacement_token"}:
                definition_id = item.metadata.get("macroDefinitionEvidenceId")
                if not isinstance(definition_id, str) or definition_id not in definitions:
                    diagnostics.append(
                        _diagnostic(
                            "normalization.invalid-macro-definition-reference",
                            "Macro attachment references an unknown definition Evidence",
                            error=True,
                        )
                    )
                    fatal = True
                    continue
            if item.kind == "enum_member_declaration":
                declaration_id = item.metadata.get("enumDeclarationEvidenceId")
                if not isinstance(declaration_id, str) or declaration_id not in enum_declarations:
                    diagnostics.append(_diagnostic("normalization.invalid-enum-declaration-reference", "Enum member references an unknown enum declaration Evidence", error=True))
                    fatal = True
                    continue
            if item.kind == "enum_member_reference":
                member_ids = item.metadata.get("enumMemberDeclarationEvidenceIds", ())
                if not isinstance(member_ids, tuple) or any(not isinstance(value, str) or value not in enum_members for value in member_ids):
                    diagnostics.append(_diagnostic("normalization.invalid-enum-member-reference", "Enum reference contains an unknown member declaration Evidence", error=True))
                    fatal = True
                    continue
            normalized_kind = "compiler_argument" if item.kind == "compiler_argument" else _KIND_MAP.get(item.kind)
            if normalized_kind is None:
                diagnostics.append(
                    _diagnostic(
                        "normalization.unsupported-evidence-kind",
                        f"Evidence kind is not normalized: {item.kind}",
                    )
                )
                continue
            if not isinstance(item.value, str):
                diagnostics.append(_diagnostic("normalization.non-string-value", f"Evidence value is not textual: {item.kind}"))
                continue
            try:
                canonical = _canonicalize(normalized_kind, item.value)
            except ValueError:
                diagnostics.append(_diagnostic("normalization.empty-value", f"Evidence has no canonical value: {item.kind}"))
                continue
            scope = _scope(item)
            key = (normalized_kind, item.subject_id, canonical, scope)
            groups[key].append(item)
            context_id = item.metadata.get("compilationContextId")
            if isinstance(context_id, str):
                context_ids[key].add(context_id)
            fact_metadata: dict[str, object] = {"identityVersion": 1, "evidenceKind": item.kind}
            for field in (
                "macroDefinitionEvidenceId",
                "callEvidenceId",
                "argumentOrdinal",
                "macroCall",
                "preprocessorRegion",
                "sourceOrder",
                "functionLike",
                "ordinal",
                "tokenRole",
                "unsupportedSemantics",
                "enumName",
                "memberName",
                "qualifiedName",
                "enumStyle",
                "enumDeclarationEvidenceId",
                "enumMemberDeclarationEvidenceIds",
                "initializerPresent",
                "bindingStatus",
                "referenceContext",
                "templateDependent",
                "function",
                "functionOwnerEvidenceId",
                "functionInventory",
                "functionSemantics",
                "usageScope",
            ):
                if field in item.metadata:
                    fact_metadata[field] = item.metadata[field]
            metadata.setdefault(key, fact_metadata)
            definition_id = item.metadata.get("macroDefinitionEvidenceId")
            if isinstance(definition_id, str):
                attachment_definition_ids[key].add(definition_id)

        facts: list[NormalizedFact] = []
        for key in sorted(groups):
            kind, subject_id, canonical, scope = key
            items = groups[key]
            fact_id = stable_id("normalized_fact", 1, kind, subject_id, canonical, scope)
            try:
                fact_metadata, conflict = merge_metadata(items, metadata[key])
                if conflict:
                    diagnostics.append(_diagnostic("normalization.function-producer-conflict", "Function producers disagree; all source records are retained"))
                if kind == "usage_scope":
                    fact_metadata, usage_conflict = merge_usage(items, fact_metadata)
                    if len(context_ids[key]) == 1:
                        fact_metadata["compilationContextId"] = next(iter(context_ids[key]))
                    if usage_conflict:
                        diagnostics.append(_diagnostic("normalization.usage-producer-conflict",
                            "用途来源存在冲突，保留未知状态 / Usage producers disagree; retain unknown"))
                if attachment_definition_ids[key]:
                    fact_metadata["macroDefinitionEvidenceIds"] = tuple(sorted(attachment_definition_ids[key]))
                facts.append(
                    NormalizedFact(
                        id=fact_id,
                        kind=kind,
                        subject_id=subject_id,
                        canonical_value=canonical,
                        scope=scope,
                        evidence_ids=tuple(item.id for item in items),
                        context_ids=tuple(context_ids[key]),
                        producers=tuple(item.producer for item in items),
                        metadata=fact_metadata,
                    )
                )
            except (TypeError, ValueError) as exc:
                diagnostics.append(_diagnostic("normalization.invalid-fact", f"Normalized fact is invalid: {type(exc).__name__}", error=True))
                fatal = True
        if fatal:
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=tuple(diagnostics))
        snapshot = NormalizedSnapshot(
            entities=frontend.entities,
            evidence=tuple(sorted({item.id: item for item in evidence}.values(), key=lambda item: item.id)),
            facts=tuple(sorted(facts, key=lambda item: (item.kind, item.scope, item.canonical_value, item.id))),
        )
        status = CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE
        return StageResult(value=snapshot, status=status, diagnostics=tuple(diagnostics))

    @staticmethod
    def _compiler_argument_evidence(
        context: ScanContext,
        frontend: FrontendSnapshot,
    ) -> tuple[tuple[Evidence, ...], tuple[Diagnostic, ...]]:
        by_path = {item.name: item for item in frontend.entities if item.kind == "source_file"}
        result: list[Evidence] = []
        diagnostics: list[Diagnostic] = []
        for unit in context.compile_contexts:
            try:
                relative_path = normalize_project_path(unit.path, context.input_root)
            except ValueError:
                diagnostics.append(_diagnostic("normalization.context-outside-workspace", "Compilation context is outside the workspace"))
                continue
            entity = by_path.get(relative_path)
            if entity is None:
                diagnostics.append(_diagnostic("normalization.context-subject-missing", f"No source Entity exists for compilation context: {relative_path}"))
                continue
            context_id = compilation_context_id(unit, context.input_root)
            for index, token in enumerate(unit.tokens):
                if index == 0 or not token:
                    continue
                value = token[:512]
                result.append(
                    Evidence(
                        id=stable_id("compiler_argument_evidence", 1, entity.id, context_id, index, value),
                        kind="compiler_argument",
                        subject_id=entity.id,
                        value=value,
                        producer="compilation-database-reader",
                        parse_mode="compile_context",
                        confidence="high",
                        metadata={
                            "identityVersion": 1,
                            "compilationContextId": context_id,
                            "tokenIndex": index,
                        },
                    )
                )
        return tuple(result), tuple(diagnostics)


def _canonicalize(kind: str, value: str) -> str:
    fact_kind = {
        "include": "headers",
        "compiler_argument": "compilerFlags",
    }.get(kind, kind)
    return canonicalize_fact_value(fact_kind, value if kind in {"inline_asm", "declaration_attribute"} else value[:512])


def _scope(evidence: Evidence) -> str:
    token_index = evidence.metadata.get("tokenIndex")
    context_id = evidence.metadata.get("compilationContextId")
    if evidence.kind == "compiler_argument" and isinstance(context_id, str) and isinstance(token_index, int):
        return f"compile:{context_id}:{token_index}"
    if evidence.location is None:
        return f"subject:{evidence.subject_id}"
    start = evidence.location.start
    end = evidence.location.end
    scope = f"source:{start.path}:{start.line}:{start.column or 0}:{end.line}:{end.column or 0}"
    if evidence.kind in {"inline_asm", "declaration_attribute", "function_declaration", "function_semantics", "usage_scope", "macro_argument_token"} and isinstance(context_id, str):
        return f"{scope}:context:{context_id}"
    return scope


def _diagnostic(code: str, message: str, *, error: bool = False) -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="normalization",
        severity=DiagnosticSeverity.ERROR if error else DiagnosticSeverity.WARNING,
        message=message,
        producer="cpp-evidence-normalizer",
        affects_exit_code=error,
    )
