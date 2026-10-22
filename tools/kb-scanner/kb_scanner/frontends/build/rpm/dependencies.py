"""RPM dependency fields, separate selection from dependency architecture."""
from __future__ import annotations
import re

from .conditions import conjunction
from .macros import ARCH_MACROS

FIELD = re.compile(r"^\s*(Requires|BuildRequires|Recommends)(\([^)]*\))?\s*:\s*(.+)$", re.I)
CONSTRAINT = re.compile(r"^\s*(ExclusiveArch|ExcludeArch)\s*:\s*(.+)$", re.I)


def parse_dependency(raw, line, env, records, **context):
    match = FIELD.match(raw)
    if not match:
        return False
    name, qualifier, body = match.groups()
    # Rich dependency expressions stay indivisible. Parentheses in capability names are fine.
    rich = body.startswith("(") or bool(re.search(r"\s(?:and|or|if|unless|with|without|else)\s", body))
    parts = [(body, match.start(3))] if rich else _parts(body, match.start(3))
    for text, offset in parts:
        expanded = records.expand(env, text, line, offset + 1, **context)
        names = expanded.names
        explicit = re.search(r"\(x86-(?:32|64)\)", expanded.text or "") is not None
        shaped = re.search(r"(?i)(?:^|[_.-])(?:x86(?:_64)?|amd64|i[3-6]86|avx\w*|sse\w*)(?:$|[_.-])", text)
        expanded_x86 = bool(re.search(r"(?i)(?:x86|amd64|i[3-6]86)",expanded.text or ""))
        target_adaptive = bool(set(names) & ARCH_MACROS) and expanded.text is not None and not expanded_x86 and not explicit and not shaped
        reason = "rpm-rich-dependency-unsupported" if rich else expanded.reason
        records.emit("build_dependency", text, line, offset + 1, **{
            **context, "parents": (*context.get("parents", ()), *expanded.refs),
            "active": conjunction(context.get("active", True), None if reason else True),
        }, field=name, qualifier=qualifier or "", softDependency=name.lower() == "recommends",
            architectureRelated=bool(set(names) & ARCH_MACROS) or explicit or bool(shaped),
            targetAdaptive=target_adaptive and not rich, x86Confirmed=explicit and not rich,
            valueKnown=expanded.text is not None and not rich, resolvedValue=expanded.text,
            macroNames=names, reason=reason)
        if rich:
            records.diagnostics.append(f"{records.path}:{line}: {reason}")
    return True


def _parts(body, offset):
    # Keep whitespace inside %{...}; versions stay attached to their dependency name.
    tokens = []
    start = None
    depth = 0
    for index, char in enumerate(body):
        if char == "{" and (depth or (index and body[index - 1] == "%")):
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        if depth == 0 and (char.isspace() or char == ","):
            if start is not None:
                tokens.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        tokens.append((start, len(body)))
    result = []
    index = 0
    while index < len(tokens):
        start, end = tokens[index]
        if index + 2 < len(tokens) and body[slice(*tokens[index + 1])] in {"=", ">", "<", ">=", "<=", "=="}:
            index += 2
            end = tokens[index][1]
        result.append((body[start:end], offset + start))
        index += 1
    return result


def parse_constraint(raw, line, env, records, **context):
    match = CONSTRAINT.match(raw)
    if not match:
        return False
    name, body = match.groups()
    value = records.expand(env, body, line, match.start(2) + 1, **context)
    allowed = None
    if value.text is not None:
        arches = value.text.split()
        allowed = env.target in arches or (env.target.startswith("riscv") and "riscv" in arches)
        if name.lower() == "excludearch":
            allowed = not allowed
    records.emit("build_arch_constraint", body, line, match.start(2) + 1, **{
        **context, "parents": (*context.get("parents", ()), *value.refs),
    }, field=name, targetAllowed=allowed, valueKnown=allowed is not None,
        architectureRelated=True, requiredSelection=True, reason=value.reason)
    return True
