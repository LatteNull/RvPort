from __future__ import annotations

from collections.abc import Iterable
from bisect import bisect_right
from itertools import accumulate
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
import re

from tree_sitter import Language, Parser
import tree_sitter_c
import tree_sitter_cpp

from ...core import (
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    ScanContext,
    SourceSpan,
    StageResult,
)
from .source_positions import SourceByteIndex
from .vocabulary import make_evidence
from .function_inventory import inventory
from .usage_inventory import collect as collect_usage
from .test_inventory import collect as collect_test_content
from .macro_records import event_metadata, call_records
from .workspace import language_candidates_for_path


_MACRO_TOKEN = re.compile(
    rb'/\*[\s\S]*?\*/|//[^\n]*|##|\.\.\.|(?:u8|u|U|L)?"(?:\\.|[^"\\])*"|(?:u8|u|U|L)?\'(?:\\.|[^\'\\])*\'|'
    rb"[A-Za-z_][A-Za-z0-9_]*|0[xX][0-9A-Fa-f]+|[0-9]+(?:\.[0-9]+)?|[^\s]"
)
_IDENTIFIER = re.compile(rb"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class _ParseCandidate:
    language: str
    language_source: str
    producer: str
    evidence: tuple[Evidence, ...]
    diagnostics: tuple[Diagnostic, ...]
    error_count: int


class TreeSitterCppAdapter:
    __slots__ = ()

    def analyze_file(
        self,
        context: ScanContext,
        workspace_root: Path,
        relative_path: str,
        entity: Entity,
        *, usage_selector=None, test_record_limit=10000,
    ) -> StageResult[tuple[Evidence, ...]]:
        source_path = (workspace_root / relative_path).resolve()
        try:
            source = source_path.read_bytes()
        except OSError as exc:
            diagnostic = Diagnostic(
                code="tree-sitter.read-failed",
                stage="frontend.tree-sitter",
                severity=DiagnosticSeverity.WARNING,
                message=f"Could not read C/C++ input {relative_path}: {type(exc).__name__}",
                producer="tree-sitter-cpp-adapter",
            )
            return StageResult(value=(), status=CompletionStatus.PARTIAL, diagnostics=(diagnostic,))

        languages, language_source = _select_languages(relative_path, context, workspace_root)
        candidates: list[_ParseCandidate] = []
        try:
            for language in languages:
                candidates.append(
                    self._parse_candidate(
                        source,
                        relative_path,
                        entity,
                        language,
                        language_source,
                        context.include_comment_hints,
                        **({"usage_selector": usage_selector} if usage_selector is not None else {}),
                        **({"test_record_limit": test_record_limit} if test_record_limit < 10000 else {}),
                    )
                )
        except Exception as exc:  # noqa: BLE001 - adapter initialization failure is isolated
            diagnostic = Diagnostic(
                code="tree-sitter.initialization-failed",
                stage="frontend.tree-sitter",
                severity=DiagnosticSeverity.ERROR,
                message=f"Tree-sitter baseline could not initialize: {type(exc).__name__}",
                producer="tree-sitter-cpp-adapter",
                affects_exit_code=True,
            )
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(diagnostic,))
        selected = min(candidates, key=lambda item: (item.error_count, 0 if item.language == "cpp" else 1))
        status = CompletionStatus.PARTIAL if selected.error_count else CompletionStatus.COMPLETE
        return StageResult(value=selected.evidence, status=status, diagnostics=selected.diagnostics)

    def _parse_candidate(
        self,
        source: bytes,
        relative_path: str,
        entity: Entity,
        language: str,
        language_source: str,
        include_comments: bool,
        *, usage_selector=None, test_record_limit=10000,
    ) -> _ParseCandidate:
        grammar = tree_sitter_c if language == "c" else tree_sitter_cpp
        grammar_package = "tree-sitter-c" if language == "c" else "tree-sitter-cpp"
        producer = f"tree-sitter-{language}@{version(grammar_package)}"
        parser = Parser(Language(grammar.language()))
        tree = parser.parse(source)
        root = tree.root_node
        positions = SourceByteIndex.build(relative_path, source)
        errors = tuple(
            (int(node.start_byte), int(node.end_byte), str(node.type))
            for node in _walk(root)
            if node.is_error or node.is_missing
        )
        macro_names = _macro_names(_walk(root), source)
        evidence: list[Evidence] = list(
            _enum_evidence(
                root,
                source,
                positions,
                entity.id,
                producer,
                language,
                language_source,
                bool(errors),
            )
        )
        unsupported_macro_semantics: set[str] = set()
        unsupported_asm: set[str] = set()
        macro_record_count = 0
        for node in _walk(root):
            kind = _node_kind(node, source, include_comments)
            # This substring check only diagnoses unknown grammar, never emits Evidence.
            if "asm" in node.type and kind != "inline_asm" and not _has_construct_ancestor(node, {"gnu_asm_expression"}):
                unsupported_asm.add(str(node.type))
            if kind is None and node.type == "identifier":
                identifier = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                if identifier in macro_names and not _has_preprocessor_definition_ancestor(node):
                    kind = "macro_expansion"
            if kind == "call_expression" and _has_preprocessor_definition_ancestor(node):
                kind = None
            if kind is None:
                continue
            value = _node_value(node, source, kind)
            span = _node_span(positions, node)
            structure = event_metadata(node, source, positions)
            if kind in {"inline_asm", "declaration_attribute", "preprocessor_condition", "macro_definition"}:
                relevant = (node.child_by_field_name("condition") or node.child_by_field_name("name") or node) if kind == "preprocessor_condition" else node
                structure["structureComplete"] = not any(
                    (start <= relevant.end_byte and end >= relevant.start_byte)
                    or (error_type == "#endif" and node.start_byte <= start <= node.end_byte)
                    for start, end, error_type in errors
                )
            undef = re.match(rb"#\s*undef\s+([A-Za-z_]\w*)", source[node.start_byte:node.end_byte]) if node.type == "preproc_call" else None
            if undef:
                structure["macroUndefName"] = undef.group(1).decode("ascii")
            item = make_evidence(
                kind=kind,
                subject_id=entity.id,
                value=value,
                producer=producer,
                parse_mode="tree_sitter_baseline",
                confidence="high" if not errors else "medium",
                span=span,
                metadata={
                    "nodeType": node.type,
                    "language": language,
                    "languageSource": language_source,
                    **({"conditionNegated": bool(re.match(rb"#\s*ifndef\b", source[node.start_byte:node.end_byte]))} if kind == "preprocessor_condition" else {}),
                    **structure,
                },
            )
            if kind == "call_expression":
                call_data, call_tokens = call_records(node, source, positions, item,
                    token_limit=min(4096, max(0, 100000 - macro_record_count)))
                macro_record_count += call_data.get('tokenCount', 0)
                if call_data.get('reason') == 'macro-token-budget':
                    unsupported_macro_semantics.add('macro-token-budget')
                item = replace(item, metadata={**item.metadata, "macroCall": call_data})
                evidence.extend(call_tokens)
            evidence.append(item)
            if kind == "macro_definition":
                attachments, unsupported = _macro_attachments(
                    node,
                    source,
                    relative_path,
                    entity.id,
                    item,
                    producer,
                    language,
                    language_source,
                    bool(errors),
                    positions,
                )
                evidence.extend(attachments)
                unsupported_macro_semantics.update(unsupported)
        evidence = inventory(root, source, positions, entity.id, producer, language, evidence, errors)
        anchors = tuple(item for item in evidence if item.kind in {
            "enum_member_declaration", "enum_member_reference", "macro_expansion"})
        if anchors and usage_selector is not None:
            anchors = usage_selector.select(entity, evidence)
        evidence = (*evidence, *collect_usage(root, source, positions, entity.id, producer, anchors))
        test_anchors = usage_selector.test_anchors(evidence, anchors) if hasattr(usage_selector, "test_anchors") else tuple(
            item for item in evidence if item.kind in {"call_expression", "inline_asm", "enum_member_reference"})
        evidence = (*evidence, *collect_test_content(root, source, positions, entity.id, producer, test_anchors,
                                                   limit=test_record_limit))
        deduplicated = {item.id: item for item in evidence}
        diagnostics: list[Diagnostic] = []
        if errors:
            first_start, _, _ = errors[0]
            diagnostics.append(
                Diagnostic(
                    code="tree-sitter.partial-parse",
                    stage="frontend.tree-sitter",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Tree-sitter retained partial Evidence for {relative_path}",
                    location=positions.location(first_start),
                    producer=producer,
                    details={"errorCount": len(errors), "language": language, "unsupportedAsmNodeTypes": tuple(sorted(unsupported_asm))},
                )
            )
        elif unsupported_asm:
            diagnostics.append(Diagnostic(
                code="tree-sitter.unsupported-asm-structure", stage="frontend.tree-sitter",
                severity=DiagnosticSeverity.WARNING, message="Unsupported asm structure retained as an analysis limitation",
                producer=producer, details={"nodeTypes": tuple(sorted(unsupported_asm))},
            ))
        if unsupported_macro_semantics:
            diagnostics.append(
                Diagnostic(
                    code="tree-sitter.unsupported-macro-semantics",
                    stage="frontend.tree-sitter",
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Macro replacement uses unsupported preprocessing semantics in {relative_path}",
                    producer=producer,
                    details={"semantics": sorted(unsupported_macro_semantics)},
                )
            )
        return _ParseCandidate(
            language=language,
            language_source=language_source,
            producer=producer,
            evidence=tuple(deduplicated.values()),
            diagnostics=tuple(diagnostics),
            error_count=len(errors) + (1 if unsupported_macro_semantics or unsupported_asm else 0),
        )


def _macro_attachments(
    node,
    source: bytes,
    relative_path: str,
    subject_id: str,
    definition: Evidence,
    producer: str,
    language: str,
    language_source: str,
    partial_parse: bool,
    positions: SourceByteIndex | None = None,
) -> tuple[tuple[Evidence, ...], tuple[str, ...]]:
    positions = positions or SourceByteIndex.build(relative_path, source)
    name = node.child_by_field_name("name")
    if name is None:
        return (), ()
    raw_after_name = source[name.end_byte : node.end_byte]
    is_function_like = node.type == "preproc_function_def"
    parameters: list[tuple[bytes, int, int]] = []
    body_start = name.end_byte
    if is_function_like:
        open_offset = raw_after_name.find(b"(")
        close_offset = raw_after_name.find(b")", open_offset + 1) if open_offset >= 0 else -1
        if open_offset < 0 or close_offset < 0:
            return (), ("unparseable-parameters",)
        parameter_start = name.end_byte + open_offset + 1
        parameter_bytes = raw_after_name[open_offset + 1 : close_offset]
        for match in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]*|\.\.\.", parameter_bytes):
            parameters.append((match.group(0), parameter_start + match.start(), parameter_start + match.end()))
        body_start = name.end_byte + close_offset + 1

    parameter_names = {value.decode("utf-8", errors="replace") for value, _, _ in parameters if value != b"..."}
    unsupported: set[str] = set()
    if any(value == b"..." for value, _, _ in parameters):
        unsupported.add("variadic")
    attachments: list[Evidence] = []
    common = {
        "nodeType": node.type,
        "language": language,
        "languageSource": language_source,
        "macroDefinitionEvidenceId": definition.id,
    }
    for ordinal, (value, start, end) in enumerate(parameters):
        text = value.decode("utf-8", errors="replace")
        attachments.append(
            make_evidence(
                kind="macro_parameter",
                subject_id=subject_id,
                value=text,
                producer=producer,
                parse_mode="tree_sitter_baseline",
                confidence="medium" if partial_parse or text == "..." else "high",
                span=positions.span(start, end),
                metadata={**common, "ordinal": ordinal, "tokenRole": "variadic" if text == "..." else "parameter"},
            )
        )

    body = source[body_start : node.end_byte]
    tokens = tuple(_MACRO_TOKEN.finditer(body))
    for match in tokens:
        text = match.group(0).decode("utf-8", errors="replace")
        if text in {"##", "#", "...", "__VA_ARGS__"}:
            unsupported.add(
                {"##": "token-pasting", "#": "stringification", "...": "variadic", "__VA_ARGS__": "variadic"}[text]
            )
    token_ordinal = 0
    for index, match in enumerate(tokens):
        raw = match.group(0)
        if raw == b"\\":
            continue
        text = raw.decode("utf-8", errors="replace")
        role = _macro_token_role(raw, body, match.end(), parameter_names)
        start = body_start + match.start()
        end = body_start + match.end()
        attachments.append(
            make_evidence(
                kind="macro_replacement_token",
                subject_id=subject_id,
                value=text,
                producer=producer,
                parse_mode="tree_sitter_baseline",
                confidence="medium" if partial_parse or unsupported else "high",
                span=positions.span(start, end),
                metadata={
                    **common,
                    "ordinal": token_ordinal,
                    "tokenRole": role,
                    "unsupportedSemantics": tuple(sorted(unsupported)),
                },
            )
        )
        token_ordinal += 1
    return tuple(attachments), tuple(sorted(unsupported))


def _macro_token_role(raw: bytes, body: bytes, end: int, parameter_names: set[str]) -> str:
    text = raw.decode("utf-8", errors="replace")
    if raw.startswith((b'/*', b'//')):
        return 'comment'
    if text in parameter_names:
        return "parameter_reference"
    if _IDENTIFIER.fullmatch(raw):
        return "call_candidate" if body[end:].lstrip().startswith(b"(") else "identifier"
    if raw[:1].isdigit():
        return "number"
    if raw.startswith((b'"', b"'", b'u8"', b'u"', b'U"', b'L"')):
        return "string"
    return "operator"


def _span_from_byte_range(relative_path: str, source: bytes, start: int, end: int) -> SourceSpan:
    return SourceByteIndex.build(relative_path, source).span(start, end)


def _select_languages(
    relative_path: str,
    context: ScanContext,
    workspace_root: Path,
) -> tuple[tuple[str, ...], str]:
    candidates = language_candidates_for_path(relative_path, context.languages)
    if len(candidates) == 1:
        return candidates, "suffix"
    direct_contexts = []
    for item in context.compile_contexts:
        try:
            unit_path = item.path.relative_to(workspace_root.resolve()).as_posix()
        except ValueError:
            continue
        if unit_path == relative_path:
            direct_contexts.append(item)
    inferred = _language_from_contexts(direct_contexts)
    if inferred is not None and inferred in candidates:
        return (inferred,), "compilation_context"
    return candidates or ("cpp",), "ambiguous_header"


def _language_from_contexts(contexts: list) -> str | None:
    for context in contexts:
        tokens = context.tokens
        for index, token in enumerate(tokens):
            value = tokens[index + 1] if token == "-x" and index + 1 < len(tokens) else token.removeprefix("-x")
            if value in {"c", "objective-c"}:
                return "c"
            if value in {"c++", "objective-c++"}:
                return "cpp"
        if context.compiler and "++" in context.compiler:
            return "cpp"
    return None


def _walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _node_kind(node, source: bytes, include_comments: bool) -> str | None:
    if node.type in {"preproc_if", "preproc_ifdef", "preproc_ifndef", "preproc_elif"}:
        return "preprocessor_condition"
    if node.type == "preproc_else":
        return "preprocessor_branch"
    if node.type == "preproc_include":
        return "include"
    if node.type in {"preproc_def", "preproc_function_def"}:
        return "macro_definition"
    if node.type == "preproc_call":
        return "macro_expansion"
    if node.type == "call_expression":
        return "call_expression"
    if node.type in {"type_identifier", "sized_type_specifier"}:
        return "type_reference"
    if node.type == "template_declaration":
        return "template_declaration"
    if node.type == "gnu_asm_expression" and not _has_construct_ancestor(node, {"gnu_asm_expression"}):
        return "inline_asm"
    if node.type in {"attribute_specifier", "attribute_declaration", "ms_declspec_modifier"} and not _has_construct_ancestor(node, {"attribute_specifier", "attribute_declaration", "ms_declspec_modifier"}):
        return "declaration_attribute"
    if node.type == "comment" and include_comments:
        return "comment"
    return None


def _has_construct_ancestor(node, kinds: set[str]) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in kinds:
            return True
        parent = parent.parent
    return False


def _node_value(node, source: bytes, kind: str) -> str:
    fields = {
        "preprocessor_condition": ("condition", "name"),
        "include": ("path",),
        "macro_definition": ("name",),
        "macro_expansion": ("directive", "name"),
        "call_expression": ("function",),
        "type_reference": ("name",),
        "selection_condition": ("condition", "value"),
    }.get(kind, ())
    for field_name in fields:
        child = node.child_by_field_name(field_name)
        if child is not None:
            value = source[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
            return value.strip('<>"') if kind == "include" else value
    raw = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    if kind == "preprocessor_branch":
        return "else"
    return raw if kind in {"inline_asm", "declaration_attribute"} else raw[:512]


def _enum_evidence(
    root,
    source: bytes,
    positions: SourceByteIndex,
    subject_id: str,
    producer: str,
    language: str,
    language_source: str,
    partial_parse: bool,
) -> tuple[Evidence, ...]:
    """Extract only declarations and references that can bind to a local enum member."""
    common = {"language": language, "languageSource": language_source}
    declarations: list[Evidence] = []
    members: list[Evidence] = []
    by_qualified: dict[tuple[str, str], list[Evidence]] = {}
    by_member: dict[str, list[Evidence]] = {}
    enum_ranges: list[tuple[int, int]] = []
    for node in _walk(root):
        if node.type != "enum_specifier":
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        enum_name = _text(source, name_node)
        enum_ranges.append((node.start_byte, node.end_byte))
        scoped = source[node.start_byte : name_node.start_byte].strip().startswith((b"enum class", b"enum struct"))
        declaration = make_evidence(
            kind="enum_declaration",
            subject_id=subject_id,
            value=enum_name,
            producer=producer,
            parse_mode="tree_sitter_baseline",
            confidence="medium" if partial_parse else "high",
            span=_node_span(positions, name_node),
            metadata={**common, "nodeType": node.type, "enumName": enum_name, "enumStyle": "scoped" if scoped else "unscoped", "bindingStatus": "partial" if partial_parse else "complete"},
        )
        declarations.append(declaration)
        for child in _walk(node):
            if child.type != "enumerator":
                continue
            member_node = child.child_by_field_name("name") or (child.named_children[0] if child.named_children else None)
            if member_node is None:
                continue
            member_name = _text(source, member_node)
            qualified = f"{enum_name}::{member_name}"
            item = make_evidence(
                kind="enum_member_declaration",
                subject_id=subject_id,
                value=qualified,
                producer=producer,
                parse_mode="tree_sitter_baseline",
                confidence="medium" if partial_parse else "high",
                span=_node_span(positions, member_node),
                metadata={
                    **common,
                    "nodeType": child.type,
                    "enumName": enum_name,
                    "memberName": member_name,
                    "qualifiedName": qualified,
                    "enumDeclarationEvidenceId": declaration.id,
                    "enumStyle": "scoped" if scoped else "unscoped",
                    "initializerPresent": child.child_by_field_name("value") is not None,
                    "bindingStatus": "partial" if partial_parse else "complete",
                },
            )
            members.append(item)
            by_qualified.setdefault((enum_name, member_name), []).append(item)
            by_member.setdefault(member_name, []).append(item)

    references: list[Evidence] = []
    guards: dict[tuple[str, str, int, int, int, int], dict[str, object]] = {}
    ordered_ranges = sorted(enum_ranges)
    range_starts = tuple(start for start, _ in ordered_ranges)
    range_ends = tuple(accumulate((end for _, end in ordered_ranges), max))
    for node in _walk(root):
        containing = bisect_right(range_starts, node.start_byte) - 1
        if containing >= 0 and node.start_byte < range_ends[containing]:
            continue
        enum_name: str | None = None
        member_name: str | None = None
        target_node = node
        guard = _selection_guard(node, source)
        if node.type == "qualified_identifier":
            scope_node = node.child_by_field_name("scope")
            name_node = node.child_by_field_name("name")
            if scope_node is None or name_node is None:
                continue
            enum_name, member_name, target_node = _text(source, scope_node).split("::")[-1], _text(source, name_node), name_node
            candidates = by_qualified.get((enum_name, member_name), [])
        elif node.type == "identifier" and guard is not None and not _has_ancestor(node, "qualified_identifier"):
            member_name = _text(source, node)
            candidates = by_member.get(member_name, [])
            if len(candidates) == 1:
                enum_name = str(candidates[0].metadata["enumName"])
        else:
            continue
        if not candidates:
            continue
        binding = "complete" if len(candidates) == 1 and not partial_parse else "ambiguous" if len(candidates) > 1 else "partial"
        qualified = f"{enum_name}::{member_name}" if enum_name else member_name or ""
        reference = make_evidence(
            kind="enum_member_reference",
            subject_id=subject_id,
            value=qualified,
            producer=producer,
            parse_mode="tree_sitter_baseline",
            confidence="high" if binding == "complete" else "medium",
            span=_node_span(positions, target_node),
            metadata={
                **common,
                "nodeType": node.type,
                "enumName": enum_name or "",
                "memberName": member_name or "",
                "qualifiedName": qualified,
                "enumMemberDeclarationEvidenceIds": tuple(sorted(item.id for item in candidates)),
                "bindingStatus": binding,
                "referenceContext": guard[1] if guard is not None else "reference",
                "templateDependent": _has_ancestor(node, "template_declaration"),
            },
        )
        references.append(reference)
        if guard is not None:
            key = guard[:6]
            snapshot = guards.setdefault(
                key,
                {
                    "nodeType": guard[6],
                    "templateDependent": guard[7],
                    "referenceIds": set(),
                    "bindings": set(),
                },
            )
            snapshot["referenceIds"].add(reference.id)  # type: ignore[union-attr]
            snapshot["bindings"].add(binding)  # type: ignore[union-attr]

    conditions: list[Evidence] = []
    for key, snapshot in sorted(guards.items()):
        kind, context, start, end, guard_start, guard_end = key
        bindings = snapshot["bindings"]
        binding = "complete" if bindings == {"complete"} else "ambiguous" if "ambiguous" in bindings else "partial"
        conditions.append(
            make_evidence(
                kind=kind,
                subject_id=subject_id,
                value=source[start:end].decode("utf-8", errors="replace")[:512],
                producer=producer,
                parse_mode="tree_sitter_baseline",
                confidence="high" if binding == "complete" else "medium",
                span=positions.span(start, end),
                metadata={
                    **common,
                    "nodeType": snapshot["nodeType"],
                    "selectionContext": context,
                    "guardStartLine": positions.location(guard_start).line,
                    "guardEndLine": positions.location(guard_end).line,
                    "templateDependent": snapshot["templateDependent"],
                    "bindingStatus": binding,
                    "enumMemberReferenceEvidenceIds": tuple(sorted(snapshot["referenceIds"])),
                },
            )
        )
    return tuple(declarations + members + references + conditions)


def _text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _has_ancestor(node, kind: str) -> bool:
    current = node.parent
    while current is not None:
        if current.type == kind:
            return True
        current = current.parent
    return False


def _selection_guard(node, source: bytes) -> tuple[str, str, int, int, int, int, str, bool] | None:
    current = node.parent
    while current is not None:
        if current.type == "case_statement":
            value = current.child_by_field_name("value")
            if value is not None and value.start_byte <= node.start_byte < value.end_byte:
                return (
                    "selection_condition",
                    "switch_case",
                    int(value.start_byte),
                    int(value.end_byte),
                    int(current.start_byte),
                    int(current.end_byte),
                    str(current.type),
                    _has_ancestor(current, "template_declaration"),
                )
        if current.type == "switch_statement":
            condition = current.child_by_field_name("condition")
            if condition is not None and condition.start_byte <= node.start_byte < condition.end_byte:
                return (
                    "selection_condition",
                    "switch",
                    int(condition.start_byte),
                    int(condition.end_byte),
                    int(current.start_byte),
                    int(current.end_byte),
                    str(condition.type),
                    _has_ancestor(current, "template_declaration"),
                )
        if current.type == "if_statement":
            condition = current.child_by_field_name("condition")
            if condition is not None and condition.start_byte <= node.start_byte < condition.end_byte:
                prefix = source[current.start_byte : condition.start_byte].lstrip()
                is_constexpr = prefix.startswith(b"if constexpr")
                return (
                    "constexpr_condition" if is_constexpr else "selection_condition",
                    "if_constexpr" if is_constexpr else "if",
                    int(condition.start_byte),
                    int(condition.end_byte),
                    int(current.start_byte),
                    int(current.end_byte),
                    str(condition.type),
                    _has_ancestor(current, "template_declaration"),
                )
        current = current.parent
    return None


def _node_span(positions: SourceByteIndex, node) -> SourceSpan:
    return positions.span(int(node.start_byte), int(node.end_byte))


def _macro_names(nodes: Iterable[object], source: bytes) -> frozenset[str]:
    names: set[str] = set()
    for node in nodes:
        if node.type not in {"preproc_def", "preproc_function_def"}:
            continue
        name = node.child_by_field_name("name")
        if name is not None:
            names.add(source[name.start_byte : name.end_byte].decode("utf-8", errors="replace"))
    return frozenset(names)


def _has_preprocessor_definition_ancestor(node) -> bool:
    current = node.parent
    while current is not None:
        if current.type in {"preproc_def", "preproc_function_def"}:
            return True
        current = current.parent
    return False
