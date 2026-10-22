from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_bash

from .safety import normalize_target_arch, symbolic_uname, unsafe_constructs
from .vocabulary import BuildRecord, record_for_token


@dataclass(frozen=True, slots=True)
class AdapterResult:
    records: tuple[BuildRecord, ...] = ()
    diagnostics: tuple[str, ...] = ()
    partial: bool = False


_X86 = re.compile(r"(?i)(?:x86(?:_64)?|amd64|i[3-6]86|avx|sse)")
_RISCV = re.compile(r"(?i)riscv(?:32|64)?")
_GENERIC = re.compile(r"(?i)(?:generic|portable|scalar|fallback|default|\*)")


def parse_shell(source: str, path: str, target_arch: str) -> AdapterResult:
    tree = Parser(Language(tree_sitter_bash.language())).parse(source.encode("utf-8"))
    diagnostics = []
    if tree.root_node.has_error:
        diagnostics.append(f"tree-sitter-bash@{version('tree-sitter-bash')}: partial syntax")
    records: list[BuildRecord] = []
    for line_number, raw in enumerate(source.splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        for match in re.finditer(r"\$\(\s*uname\s+-m\s*\)|`\s*uname\s+-m\s*`", raw):
            probe = symbolic_uname(match.group(0), target_arch)
            records.append(record_for_token("build_arch_probe", "uname -m", line_number, raw, metadata={"selectionStatus": "selected", "resolvedValue": probe.value, "role": "riscv"}))
        branch = re.match(r"^\s*([^#][^)]*)\)", raw)
        if branch:
            pattern = branch.group(1).strip()
            role = _role(pattern)
            status = _branch_status(pattern, target_arch)
            records.append(record_for_token("build_branch", pattern, line_number, raw, metadata={"conditionGroup": f"{path}:case", "selectionStatus": status, "role": role}))
        assignment = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$", raw)
        if assignment:
            records.append(record_for_token("build_assignment", assignment.group(1), line_number, raw, metadata={"expression": assignment.group(2), "selectionStatus": "unknown", "role": _role(assignment.group(2))}, confidence="medium"))
    for name, line, text in _shell_unsafe(source):
        records.append(record_for_token("build_unsupported", name, line, text, metadata={"selectionStatus": "unknown", "reason": name}, confidence="medium"))
        diagnostics.append(f"{path}:{line}: {name} unsupported/unknown")
    return _result(records, diagnostics)


def parse_m4(source: str, path: str, target_arch: str) -> AdapterResult:
    del target_arch
    records: list[BuildRecord] = []
    diagnostics: list[str] = []
    allowed = {"AC_CANONICAL_HOST", "AC_CANONICAL_TARGET", "AS_CASE", "AM_CONDITIONAL", "AC_ARG_ENABLE", "AC_COMPILE_IFELSE"}
    for line_number, raw in enumerate(source.splitlines(), 1):
        text = re.sub(r"dnl.*$", "", raw).strip()
        if not text:
            continue
        for match in re.finditer(r"\b([A-Z][A-Z0-9_]*)\s*\((.*)", text):
            name, args = match.groups()
            role = _role(args)
            if name in allowed:
                records.append(record_for_token("build_condition", name, line_number, raw, metadata={"expression": args[:512], "selectionStatus": "unknown", "role": role}, confidence="medium"))
            else:
                records.append(record_for_token("build_unsupported", name, line_number, raw, metadata={"selectionStatus": "unknown", "reason": "unsupported-m4-macro"}, confidence="medium"))
                diagnostics.append(f"{path}:{line_number}: unsupported M4 macro {name}")
    for name, line, text in unsafe_constructs(source, "m4"):
        records.append(record_for_token("build_unsupported", name, line, text, metadata={"selectionStatus": "unknown", "reason": name}, confidence="medium"))
        diagnostics.append(f"{path}:{line}: {name} unsupported/unknown")
    return _result(records, diagnostics)


def parse_machine_json(source: str, path: str, input_kind: str, target_arch: str) -> AdapterResult:
    if len(source.encode("utf-8")) > 4 * 1024 * 1024:
        return AdapterResult((), (f"{path}: machine metadata exceeds size budget",), True)
    try:
        payload = json.loads(source)
    except (TypeError, json.JSONDecodeError) as exc:
        return AdapterResult((), (f"{path}: invalid JSON ({type(exc).__name__})",), True)
    records: list[BuildRecord] = []
    diagnostics: list[str] = []
    target = normalize_target_arch(target_arch)
    status = _metadata_status(payload, target)
    configuration = _configuration_name(payload)
    base = {"selectionStatus": status, "configuration": configuration, "schema": _schema(payload), "jsonPointer": "/"}
    records.append(BuildRecord("build_configuration", configuration, 1, 1, 1 + len(configuration), base, "high" if status != "unknown" else "medium"))

    if input_kind == "meson":
        targets = payload if isinstance(payload, list) else payload.get("targets", []) if isinstance(payload, dict) else []
    elif input_kind == "compilation-database":
        targets = payload if isinstance(payload, list) else []
    elif input_kind == "ctest":
        targets = payload.get("tests", []) if isinstance(payload, dict) else []
    else:
        targets = _find_targets(payload)
    for index, item in enumerate(targets if isinstance(targets, list) else []):
        if not isinstance(item, dict):
            diagnostics.append(f"{path}: target entry {index} is not an object")
            continue
        target_name = str(item.get("name") or item.get("id") or item.get("output") or item.get("file") or f"entry-{index}")
        metadata = {**base, "target": target_name, "jsonPointer": f"/{index}"}
        declared_type = str(item.get("type") or item.get("kind") or "").lower()
        if input_kind == "ctest" or item.get("is_test") is True or declared_type in {"test", "unit-test", "benchmark-test"}:
            metadata["testRole"] = "confirmed"
            metadata["testSuite"] = str(item.get("suite") or item.get("project") or configuration)
        for source_field, metadata_field in (("coverageTarget", "coverageTarget"), ("tested_source", "testedSource"), ("callTarget", "callTarget"), ("alternativeTestFor", "alternativeTestFor")):
            if isinstance(item.get(source_field), str) and item[source_field]:
                metadata[metadata_field] = item[source_field]
        records.append(BuildRecord("build_target", target_name, 1, 1, 1 + len(target_name), metadata, "high" if status != "unknown" else "medium"))
        for value in _paths(item, ("sources", "source", "filename", "file")):
            records.append(BuildRecord("build_source", value, 1, 1, 1 + len(value), metadata, "high" if status != "unknown" else "medium"))
        for value in _strings(item, ("compile_args", "compile_parameters", "arguments", "command", "fragments")):
            for token in value.split():
                if token.startswith("-"):
                    records.append(BuildRecord("build_argument", token, 1, 1, 1 + len(token), metadata, "high" if status != "unknown" else "medium"))
        for value in _strings(item, ("dependencies", "depends", "linkLibraries")):
            records.append(BuildRecord("build_dependency", value, 1, 1, 1 + len(value), metadata, "high" if status != "unknown" else "medium"))
        for value in _paths(item, ("artifacts", "outputs")):
            records.append(BuildRecord("build_artifact", value, 1, 1, 1 + len(value), metadata, "high" if status != "unknown" else "medium"))
    if input_kind == "cmake" and unsafe_constructs(source, "cmake"):
        diagnostics.append(f"{path}: execute_process text is unsupported")
    return _result(records, diagnostics)


def parse_rpm(source: str, path: str, target_arch: str) -> AdapterResult:
    from .rpm.parser import parse
    records, diagnostics = parse(source, path, target_arch)
    return AdapterResult(records, diagnostics, bool(diagnostics))


def _shell_unsafe(source: str) -> tuple[tuple[str, int, str], ...]:
    found = []
    for line, raw in enumerate(source.splitlines(), 1):
        for match in re.finditer(r"\$\(([^)]*)\)|`([^`]*)`", raw):
            command = (match.group(1) or match.group(2) or "").strip()
            if not symbolic_uname(command, "riscv64").recognized:
                found.append(("shell-command-substitution", line, raw.strip()))
    return tuple(found)


def _role(value: str) -> str:
    if _RISCV.search(value):
        return "riscv"
    if _X86.search(value):
        return "x86"
    if _GENERIC.search(value):
        return "generic"
    return "unknown"


def _branch_status(pattern: str, target_arch: str) -> str:
    role = _role(pattern)
    if role == "riscv":
        return "selected" if _RISCV.search(normalize_target_arch(target_arch)) else "inactive"
    if role == "x86":
        return "inactive"
    if role == "generic":
        return "selected"
    return "unknown"


def _metadata_status(payload: Any, target_arch: str) -> str:
    text = json.dumps(payload, sort_keys=True).lower()
    if target_arch in text or (target_arch == "riscv64" and "riscv" in text):
        return "selected"
    if _X86.search(text):
        return "inactive"
    return "unknown"


def _configuration_name(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("name") or payload.get("configuration") or payload.get("kind") or "observed")
    return "observed"


def _schema(payload: Any) -> str:
    if isinstance(payload, dict):
        version_value = payload.get("version") or payload.get("cmake") or payload.get("meson_version")
        return str(version_value)[:128] if version_value is not None else "unknown"
    return "unknown"


def _find_targets(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("targets"), list):
            return [item for item in payload["targets"] if isinstance(item, dict)]
        for value in payload.values():
            found = _find_targets(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _find_targets(value)
            if found:
                return found
    return []


def _strings(payload: Any, keys: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys:
                values.extend(_flatten_strings(value))
            elif isinstance(value, (dict, list)):
                values.extend(_strings(value, keys))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_strings(item, keys))
    return tuple(dict.fromkeys(value for value in values if value))


def _paths(payload: Any, keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in _strings(payload, keys) if not value.startswith("-"))


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(item) for key in ("path", "id", "name", "fragment") if (item := value.get(key)) is not None]
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    return []


def _stack_status(stack: list[bool | None]) -> str:
    if False in stack:
        return "inactive"
    if None in stack:
        return "unknown"
    return "selected"


def _result(records: list[BuildRecord], diagnostics: list[str]) -> AdapterResult:
    ordered = tuple(sorted({(item.kind, item.line, item.start_column, item.value, str(item.metadata)): item for item in records}.values(), key=lambda item: (item.line, item.start_column, item.kind, item.value)))
    return AdapterResult(ordered, tuple(dict.fromkeys(diagnostics)), bool(diagnostics))
