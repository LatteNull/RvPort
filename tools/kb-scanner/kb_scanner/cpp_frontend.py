from __future__ import annotations

import re
from pathlib import Path

from .models import (
    BranchInfo,
    CallFact,
    CompileCommandContext,
    ConditionFrame,
    FileFacts,
    IncludeFact,
    MacroBranchGroup,
    MacroDefinitionFact,
    ProjectFacts,
    TextFact,
)

CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
ASM_SUFFIXES = {".s", ".S", ".asm", ".inc"}
BUILD_FILE_NAMES = {
    "CMakeLists.txt",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "meson.build",
    "BUILD",
    "BUILD.bazel",
    "configure.ac",
    "build.zig",
}
BUILD_FILE_SUFFIXES = {".mk", ".cmake", ".bzl", ".am", ".m4", ".in", ".sh", ".zig", ".vcxproj", ".props", ".targets"}
RPM_SPEC_SUFFIXES = {".spec"}

INCLUDE_RE = re.compile(r"^\s*#\s*include\s*([<\"])([^>\"]+)[>\"]")
IFDEF_RE = re.compile(r"^\s*#\s*(ifdef|ifndef)\s+([A-Za-z_]\w*)")
IF_RE = re.compile(r"^\s*#\s*if\s+(.+)")
ELIF_RE = re.compile(r"^\s*#\s*elif\s+(.+)")
ELSE_RE = re.compile(r"^\s*#\s*else\b")
ENDIF_RE = re.compile(r"^\s*#\s*endif\b")
DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)(?:\(([^)]*)\))?\s*(.*)")
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
MACRO_NAME_RE = re.compile(r"\b([A-Za-z_]\w*)\b")

CONTROL_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "return",
    "sizeof",
    "defined",
    "alignas",
    "static_cast",
    "reinterpret_cast",
    "const_cast",
    "dynamic_cast",
}

X86_CONDITION_TOKENS = re.compile(
    r"(%\{\??ix86\}|%\{\??x86_64\}|\b(__x86_64__|x86_64|amd64|i[3-6]86|_M_X64|__i386__|_M_IX86|__amd64__|__SSE[0-9_]*__|__SSSE3__|__AVX[0-9A-Z_]*__)\b)",
    re.IGNORECASE,
)
RISCV_CONDITION_TOKENS = re.compile(r"(%\{\??riscv64\}|%\{\??riscv\}|\b(__riscv|__riscv__|__riscv_xlen|__riscv_vector|riscv64|riscv|rvv)\b)", re.IGNORECASE)
GENERIC_CONDITION_TOKENS = re.compile(r"\b(generic|portable|fallback|scalar|baseline)\b", re.IGNORECASE)
RPM_SECTION_RE = re.compile(r"^\s*%(prep|build|install|check|files|changelog)\b", re.IGNORECASE)
RPM_IFARCH_RE = re.compile(r"^\s*%(ifarch|ifnarch)\s+(.+)", re.IGNORECASE)
RPM_IF_RE = re.compile(r"^\s*%if\s+(.+)", re.IGNORECASE)
RPM_ELSE_RE = re.compile(r"^\s*%else\b", re.IGNORECASE)
RPM_ENDIF_RE = re.compile(r"^\s*%endif\b", re.IGNORECASE)
RPM_ARCH_HEADER_RE = re.compile(r"^\s*(ExclusiveArch|ExcludeArch)\s*:\s*(.+)", re.IGNORECASE)
RPM_MACRO_RE = re.compile(r"^\s*%(global|define)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(.*)", re.IGNORECASE)
RPM_RELEVANT_MACRO_RE = re.compile(
    r"(_target_cpu|_host_cpu|_build_cpu|optflags|build_cflags|build_cxxflags|build_ldflags|"
    r"x86_64|amd64|i[3-6]86|ix86|riscv64|riscv|"
    r"-mavx|-mavx2|-mavx512|-msse|-msse2|-msse3|-mssse3|-msse4|-mfma|-mxsave|-march=x86-64)",
    re.IGNORECASE,
)


def discover_cpp_files(root: Path, excludes: list[str], exclude_paths: list[str] | None = None) -> list[Path]:
    excluded_parts = {part for item in excludes for part in Path(item).parts if part}
    excluded_roots = _resolve_exclude_paths(root, exclude_paths or [])
    if root.is_file():
        is_cpp = root.suffix.lower() in CPP_SUFFIXES
        is_asm = root.suffix in ASM_SUFFIXES
        is_build = root.name in BUILD_FILE_NAMES or root.suffix.lower() in BUILD_FILE_SUFFIXES
        is_rpm_spec = root.suffix.lower() in RPM_SPEC_SUFFIXES
        if (is_cpp or is_asm or is_build or is_rpm_spec) and not _is_excluded(root, excluded_parts, excluded_roots):
            return [root]
        return []

    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        is_cpp = path.suffix.lower() in CPP_SUFFIXES
        is_asm = path.suffix in ASM_SUFFIXES
        is_build = path.name in BUILD_FILE_NAMES or path.suffix.lower() in BUILD_FILE_SUFFIXES
        is_rpm_spec = path.suffix.lower() in RPM_SPEC_SUFFIXES
        if not is_cpp and not is_asm and not is_build and not is_rpm_spec:
            continue
        if _is_excluded(path, excluded_parts, excluded_roots):
            continue
        result.append(path)
    return sorted(result)


def parse_project(
    root: Path,
    excludes: list[str],
    exclude_paths: list[str] | None,
    scan_mode: str,
    compile_contexts: dict[str, CompileCommandContext],
    target_arch: str = "riscv64",
    include_inactive_branches: bool = False,
    include_comment_hints: bool = True,
) -> ProjectFacts:
    files = [parse_file(path, scan_mode) for path in discover_cpp_files(root, excludes, exclude_paths)]
    compile_reachable_files = _compile_reachable_files(root, files, compile_contexts)
    return ProjectFacts(
        root=root,
        files=files,
        scan_mode=scan_mode,
        target_arch=target_arch,
        include_inactive_branches=include_inactive_branches,
        include_comment_hints=include_comment_hints,
        compile_contexts=compile_contexts,
        compile_reachable_files=compile_reachable_files,
    )


def _compile_reachable_files(
    root: Path,
    files: list[FileFacts],
    compile_contexts: dict[str, CompileCommandContext],
) -> set[str]:
    if not compile_contexts:
        return set()

    by_path = {str(file_facts.path.resolve()): file_facts for file_facts in files}
    reachable: set[str] = set()

    for source_path, context in compile_contexts.items():
        source = Path(source_path).resolve()
        if str(source) not in by_path:
            continue
        _mark_compile_reachable(source, context, by_path, reachable, root)
    return reachable


def _mark_compile_reachable(
    path: Path,
    context: CompileCommandContext,
    by_path: dict[str, FileFacts],
    reachable: set[str],
    root: Path,
) -> None:
    resolved = str(path.resolve())
    if resolved in reachable:
        return
    file_facts = by_path.get(resolved)
    if file_facts is None:
        return
    reachable.add(resolved)

    for include in file_facts.includes:
        if include.system:
            continue
        target = _resolve_project_include(include.path, file_facts.path, context, root, by_path)
        if target is not None:
            _mark_compile_reachable(target, context, by_path, reachable, root)


def _resolve_project_include(
    include_path: str,
    including_file: Path,
    context: CompileCommandContext,
    root: Path,
    by_path: dict[str, FileFacts],
) -> Path | None:
    candidates: list[Path] = [
        including_file.parent / include_path,
        root / include_path,
    ]
    for raw_dir in context.include_dirs:
        include_dir = Path(raw_dir)
        if include_dir.is_absolute():
            candidates.append(include_dir / include_path)
        else:
            candidates.append(including_file.parent / include_dir / include_path)
            candidates.append(root / include_dir / include_path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if str(resolved) in by_path:
            return resolved
    return None


def _resolve_exclude_paths(root: Path, exclude_paths: list[str]) -> list[Path]:
    project_root = root.parent if root.is_file() else root
    resolved: list[Path] = []
    for raw_path in exclude_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved.append(candidate.resolve())
    return resolved


def _is_excluded(path: Path, excluded_parts: set[str], excluded_roots: list[Path]) -> bool:
    if any(part in excluded_parts for part in path.parts):
        return True
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in excluded_roots)


def parse_file(path: Path, scan_mode: str) -> FileFacts:
    if path.suffix.lower() in RPM_SPEC_SUFFIXES:
        return parse_rpm_spec_file(path, scan_mode)

    facts = FileFacts(path=path, parse_mode=scan_mode)
    condition_stack: list[ConditionFrame] = []
    branch_group_stack: list[str] = []
    macros: dict[str, MacroDefinitionFact] = {}

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # noqa: BLE001
        facts.diagnostics.append(f"读取失败: {exc}")
        return facts

    for index, line in enumerate(lines, start=1):
        if match := IFDEF_RE.match(line):
            kind, macro = match.groups()
            group_id = _new_branch_group(facts, path, index, kind, macro)
            branch_group_stack.append(group_id)
            condition_stack.append(
                ConditionFrame(
                    kind=kind,
                    expr=macro,
                    macro=macro,
                    line=index,
                    branch_group_id=group_id,
                    branch_role=_branch_role(kind, macro),
                )
            )
        elif match := IF_RE.match(line):
            expr = match.group(1).strip()
            group_id = _new_branch_group(facts, path, index, "if", expr)
            branch_group_stack.append(group_id)
            condition_stack.append(
                ConditionFrame(
                    kind="if",
                    expr=expr,
                    macro=_first_macro(expr),
                    line=index,
                    branch_group_id=group_id,
                    branch_role=_branch_role("if", expr),
                )
            )
        elif match := ELIF_RE.match(line):
            if condition_stack:
                condition_stack.pop()
            expr = match.group(1).strip()
            group_id = branch_group_stack[-1] if branch_group_stack else _new_branch_group(facts, path, index, "elif", expr)
            _add_branch(facts, group_id, "elif", expr, index)
            condition_stack.append(
                ConditionFrame(
                    kind="elif",
                    expr=expr,
                    macro=_first_macro(expr),
                    line=index,
                    branch_group_id=group_id,
                    branch_role=_branch_role("elif", expr),
                )
            )
        elif ELSE_RE.match(line):
            if condition_stack:
                prev = condition_stack.pop()
                group_id = prev.branch_group_id
                if group_id:
                    _add_branch(facts, group_id, "else", "else", index)
                condition_stack.append(
                    ConditionFrame(
                        kind="else",
                        expr=f"!({prev.expr})",
                        macro=prev.macro,
                        line=index,
                        branch_group_id=group_id,
                        branch_role="fallback_branch",
                    )
                )
        elif ENDIF_RE.match(line):
            if condition_stack:
                frame = condition_stack.pop()
                if branch_group_stack and frame.branch_group_id == branch_group_stack[-1]:
                    branch_group_stack.pop()

        conditions = list(condition_stack)
        if match := INCLUDE_RE.match(line):
            opener, include_path = match.groups()
            facts.includes.append(
                IncludeFact(path=include_path, file=path, line=index, system=opener == "<", conditions=conditions)
            )

        if match := DEFINE_RE.match(line):
            name, params_raw, body = match.groups()
            params = [p.strip() for p in params_raw.split(",")] if params_raw is not None else None
            macro = MacroDefinitionFact(name=name, file=path, line=index, params=params, body=body, conditions=conditions)
            facts.macros.append(macro)
            macros[name] = macro

        facts.texts.append(TextFact(file=path, line=index, text=line, conditions=conditions))

        called_names: set[str] = set()
        for match in CALL_RE.finditer(line):
            name = match.group(1)
            if name in CONTROL_KEYWORDS:
                continue
            called_names.add(name)
            facts.calls.append(CallFact(name=name, file=path, line=index, text=line.strip(), conditions=conditions))

        if DEFINE_RE.match(line):
            continue
        for name in called_names:
            macro = macros.get(name)
            if not macro:
                continue
            if not macro.params or not macro.body:
                continue
            for expanded_call in CALL_RE.finditer(macro.body):
                call_name = expanded_call.group(1)
                if call_name in CONTROL_KEYWORDS:
                    continue
                facts.calls.append(
                    CallFact(
                        name=call_name,
                        file=path,
                        line=index,
                        text=line.strip(),
                        conditions=conditions,
                        via_macro=macro.name,
                        macro_definition_line=macro.line,
                    )
                )

    return facts


def parse_rpm_spec_file(path: Path, scan_mode: str) -> FileFacts:
    facts = FileFacts(path=path, parse_mode=scan_mode)
    condition_stack: list[ConditionFrame] = []
    branch_group_stack: list[str] = []
    section: str | None = None

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # noqa: BLE001
        facts.diagnostics.append(f"读取失败: {exc}")
        return facts

    for index, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        section_match = RPM_SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).lower()

        if RPM_ENDIF_RE.match(line):
            if condition_stack:
                frame = condition_stack.pop()
                if branch_group_stack and frame.branch_group_id == branch_group_stack[-1]:
                    branch_group_stack.pop()
        elif RPM_ELSE_RE.match(line):
            if condition_stack:
                prev = condition_stack.pop()
                group_id = prev.branch_group_id
                if group_id:
                    _add_branch(facts, group_id, "else", "else", index)
                condition_stack.append(
                    ConditionFrame(
                        kind="rpm_else",
                        expr=f"!({prev.expr})",
                        macro=prev.macro,
                        line=index,
                        branch_group_id=group_id,
                        branch_role="fallback_branch",
                    )
                )
        elif match := RPM_IFARCH_RE.match(line):
            kind, expr = match.groups()
            group_id = _new_branch_group(facts, path, index, f"rpm_{kind.lower()}", expr)
            branch_group_stack.append(group_id)
            condition_stack.append(
                ConditionFrame(
                    kind=f"rpm_{kind.lower()}",
                    expr=expr.strip(),
                    macro=_first_macro(expr),
                    line=index,
                    branch_group_id=group_id,
                    branch_role=_branch_role(kind.lower(), expr),
                )
            )
        elif match := RPM_IF_RE.match(line):
            expr = match.group(1).strip()
            group_id = _new_branch_group(facts, path, index, "rpm_if", expr)
            branch_group_stack.append(group_id)
            condition_stack.append(
                ConditionFrame(
                    kind="rpm_if",
                    expr=expr,
                    macro=_first_macro(expr),
                    line=index,
                    branch_group_id=group_id,
                    branch_role=_branch_role("if", expr),
                )
            )

        metadata = {
            "sourceKind": "rpm_spec",
            "section": section,
            "comment": stripped.startswith("#"),
            "changelog": section == "changelog",
        }
        if match := RPM_ARCH_HEADER_RE.match(line):
            metadata["rpmTag"] = match.group(1)
            metadata["archTokens"] = _rpm_arch_tokens(match.group(2))
        if match := RPM_MACRO_RE.match(line):
            macro_name = match.group(2)
            macro_body = match.group(3)
            metadata["rpmMacro"] = macro_name
            metadata["rpmMacroRelevant"] = bool(RPM_RELEVANT_MACRO_RE.search(macro_name) or RPM_RELEVANT_MACRO_RE.search(macro_body))
        facts.texts.append(TextFact(file=path, line=index, text=line, conditions=list(condition_stack), metadata=metadata))

    return facts


def _first_macro(expr: str) -> str | None:
    for token in MACRO_NAME_RE.findall(expr):
        if token not in CONTROL_KEYWORDS and not token.isdigit():
            return token
    return None


def _new_branch_group(facts: FileFacts, path: Path, line: int, kind: str, expr: str) -> str:
    group_id = f"{path}:{line}"
    facts.branch_groups[group_id] = MacroBranchGroup(id=group_id, file=path, start_line=line)
    _add_branch(facts, group_id, kind, expr, line)
    return group_id


def _add_branch(facts: FileFacts, group_id: str, kind: str, expr: str, line: int) -> None:
    group = facts.branch_groups[group_id]
    group.branches.append(BranchInfo(kind=kind, expr=expr, line=line, role=_branch_role(kind, expr)))


def _branch_role(kind: str, expr: str) -> str:
    if kind == "else":
        return "fallback_branch"
    if kind == "ifnarch":
        return "fallback_branch" if X86_CONDITION_TOKENS.search(expr) else "unknown"
    if kind == "ifndef":
        return "fallback_branch" if X86_CONDITION_TOKENS.search(expr) else "unknown"
    if RISCV_CONDITION_TOKENS.search(expr):
        return "riscv_branch"
    if X86_CONDITION_TOKENS.search(expr):
        return "x86_branch"
    if GENERIC_CONDITION_TOKENS.search(expr):
        return "generic_branch"
    return "unknown"


def _rpm_arch_tokens(value: str) -> list[str]:
    tokens = re.findall(r"%\{\??[A-Za-z0-9_]+\}|[A-Za-z0-9_]+", value)
    return [token.strip() for token in tokens if token.strip()]
