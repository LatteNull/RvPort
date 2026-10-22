"""Bounded syntax inventory. Native nodes never escape this call."""
from dataclasses import replace
import re

from .vocabulary import make_evidence

_ATTRIBUTE = re.compile(rb"\b(?:__)?(?:target|target_clones|target_version|cpu_dispatch|cpu_specific)(?:__)?\s*\(")
_ATTR_TYPES = {"attribute_specifier", "attribute_declaration", "ms_declspec_modifier"}
_BOUNDARIES = {"function_definition", "lambda_expression", "class_specifier", "struct_specifier", "template_declaration"}


def walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _nested_bodies(body):
    """Keep outermost exclusions only; do not rescan their descendants."""
    stack = list(body.children)
    result = []
    while stack:
        node = stack.pop()
        if node.type in _BOUNDARIES:
            result.append((int(node.start_byte), int(node.end_byte)))
        else:
            stack.extend(node.children)
    return tuple(sorted(result))


def _coordinates(positions, interval):
    span = positions.span(*interval)
    return (span.start.line, span.start.column, span.end.line, span.end.column)


def inventory(root, source, positions, subject, producer, language, evidence, errors=(), limit=50000):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("function inventory limit must be nonnegative")
    if not _ATTRIBUTE.search(source):
        return tuple(evidence)
    records, count = [], 0
    for node in walk(root):
        if node.type not in {"function_definition", "declaration", "field_declaration"}:
            continue
        declarator = node.child_by_field_name("declarator")
        if declarator is None or declarator.type != "function_declarator":
            continue
        count += 1
        if count > limit:
            continue
        name = declarator.child_by_field_name("declarator")
        params = declarator.child_by_field_name("parameters")
        if name is None or params is None:
            continue
        raw = lambda n: source[n.start_byte:n.end_byte].decode("utf-8", errors="replace")
        body = node.child_by_field_name("body")
        attrs = []
        stack = list(reversed(node.children))
        while stack:
            child = stack.pop()
            if body is not None and child == body:
                continue
            if child.type in {"parameter_list", "lambda_expression"}:
                continue
            if child.type in _ATTR_TYPES:
                if _ATTRIBUTE.search(source[child.start_byte:child.end_byte]):
                    attrs.append((int(child.start_byte), int(child.end_byte)))
                continue
            stack.extend(reversed(child.children))
        scope, unsupported, conditional = [], name.type != "identifier", False
        parent = node.parent
        linkage = "C" if language == "c" else "C++"
        while parent is not None:
            if parent.type == "namespace_definition":
                ns = parent.child_by_field_name("name")
                scope.append(raw(ns) if ns is not None else f"anonymous@{parent.start_byte}")
            if parent.type == "linkage_specification":
                value = parent.child_by_field_name("value")
                linkage = raw(value).strip('"') if value is not None else "unknown"
                unsupported |= linkage not in {"C", "C++"}
            unsupported |= parent.type in _BOUNDARIES
            conditional |= parent.type.startswith("preproc_")
            parent = parent.parent
        parameter_types = []
        for param in params.named_children:
            if param.type not in {"parameter_declaration", "optional_parameter_declaration"}:
                unsupported = True
                parameter_types.append(raw(param))
                continue
            typ = param.child_by_field_name("type")
            decl = param.child_by_field_name("declarator")
            text = raw(param)
            if decl is not None and decl.type == "identifier":
                text = source[param.start_byte:decl.start_byte].decode("utf-8", errors="replace")
            elif decl is not None:
                unsupported = True
            unsupported |= typ is None or typ.type not in {"primitive_type", "sized_type_specifier"}
            parameter_types.append(" ".join(text.split()))
        unsupported |= language == "c" and not parameter_types
        typ = node.child_by_field_name("type")
        return_type = raw(typ) if typ is not None else "unknown"
        unsupported |= typ is None or typ.type not in {"primitive_type", "sized_type_specifier"}
        head_end = body.start_byte if body is not None else node.end_byte
        internal = bool(re.search(rb"\bstatic\b", source[node.start_byte:head_end]))
        signature = "::".join((*reversed(scope), raw(name))) + "(" + ",".join(parameter_types) + ")"
        nested = _nested_bodies(body) if body is not None else ()
        damaged = any(a <= node.end_byte and b >= node.start_byte for a, b, *_ in errors)
        records.append({"name": raw(name), "signature": signature, "returnType": return_type,
                        "linkage": linkage, "internal": internal, "attributes": attrs,
                        "declarationBytes": (int(node.start_byte), int(node.end_byte)),
                        "nameBytes": (int(name.start_byte), int(name.end_byte)),
                        "bodyBytes": (int(body.start_byte), int(body.end_byte)) if body is not None else None,
                        "nestedBytes": nested, "conditional": conditional,
                        "bindingStatus": "unknown" if unsupported or damaged else "complete"})
    relevant = {(r["signature"], r["linkage"], r["internal"]) for r in records if r["attributes"]}
    additions, owners = [], {}
    for record in records:
        if (record["signature"], record["linkage"], record["internal"]) not in relevant:
            continue
        record["inventoryTruncated"] = count > limit
        record["declarationCount"] = count
        record["language"] = language
        record["declarationSpan"] = _coordinates(positions, record["declarationBytes"])
        record["attributeSpans"] = tuple(_coordinates(positions, span) for span in record["attributes"])
        record["bodySpan"] = _coordinates(positions, record["bodyBytes"]) if record["bodyBytes"] is not None else None
        record["nestedSpans"] = tuple(_coordinates(positions, span) for span in record["nestedBytes"])
        item = make_evidence(kind="function_declaration", subject_id=subject, value=record["name"],
            producer=producer, parse_mode="tree_sitter_baseline", confidence="medium",
            span=positions.span(*record["nameBytes"]), metadata={"function": record})
        additions.append(item)
        for span in record["attributes"]:
            owners[positions.span(*span)] = item.id
    # Preserve existing IDs and values; association metadata is additive only.
    result = []
    for item in evidence:
        if item.kind != "declaration_attribute" or not _ATTRIBUTE.search(item.value.encode("utf-8")):
            result.append(item)
            continue
        metadata = {**item.metadata, "functionInventory": {
            "declarationCount": count, "retainedDeclarationCount": len(records),
            "truncated": count > limit, "bindingStatus": "bound" if item.location in owners else "unknown",
            "reason": "multiversion-budget-exceeded" if count > limit else (
                "multiversion-owner-located" if item.location in owners else "multiversion-binding-ambiguous"),
        }}
        if item.location in owners:
            metadata["functionOwnerEvidenceId"] = owners[item.location]
        result.append(replace(item, metadata=metadata))
    return tuple((*result, *additions))
