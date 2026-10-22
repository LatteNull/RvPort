from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...core import CompilationUnitContext, Diagnostic, DiagnosticSeverity
from .compilation_database import compilation_context_id


@dataclass(frozen=True, slots=True)
class ClangArgumentResult:
    accepted: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]


_SAFE_PAIRED = frozenset(
    {"-I", "-isystem", "-iquote", "-idirafter", "-D", "-U", "-x", "-target", "--target", "--sysroot", "-isysroot"}
)
_PATH_PAIRED = frozenset({"-I", "-isystem", "-iquote", "-idirafter", "--sysroot", "-isysroot"})
_UNSAFE_PAIRED = frozenset(
    {
        "-o",
        "-MF",
        "-MT",
        "-MQ",
        "-MJ",
        "-Xclang",
        "-Xlinker",
        "-Xassembler",
        "-load",
        "-plugin",
        "-add-plugin",
        "-fplugin",
        "-include",
        "-include-pch",
        "-include-pth",
        "-fmodule-file",
        "-fmodule-map-file",
        "-serialize-diagnostics",
        "--serialize-diagnostics",
        "-dependency-file",
    }
)
_UNSAFE_PREFIXES = (
    "@",
    "-fplugin=",
    "-fplugin-arg-",
    "-fmodule",
    "-fcxx-modules",
    "-fmodules",
    "-module",
    "-include-pch=",
    "-include-pth=",
    "-fmodule-file=",
    "-fmodule-map-file=",
    "-o",
    "-MF",
    "-MT",
    "-MQ",
    "-MJ",
    "-MD",
    "-MMD",
    "-MP",
    "-save-temps",
    "-ftime-trace",
    "-serialize-diagnostics",
    "--serialize-diagnostics",
    "-Wa,",
    "-Wl,",
    "-fuse-ld",
    "--offload",
    "-foffload",
    "-fopenmp-targets",
    "--cuda",
    "--hip",
)
_SAFE_EXACT = frozenset({"-nostdinc", "-nostdinc++", "-pthread", "-fsyntax-only"})
_SAFE_TARGET_PREFIXES = (
    "-march=",
    "-mcpu=",
    "-mtune=",
    "-mabi=",
    "-mfpmath=",
    "-mfloat-abi=",
    "-mno-",
    "-msse",
    "-mavx",
)


def normalize_clang_arguments(context: CompilationUnitContext, project_root: Path) -> ClangArgumentResult:
    entry_id = compilation_context_id(context, project_root)
    tokens = list(context.tokens)
    accepted: list[str] = []
    diagnostics: list[Diagnostic] = []
    index = 0
    if tokens and not tokens[0].startswith("-"):
        index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "-c":
            index += 1
            continue
        if token in _UNSAFE_PAIRED:
            value = tokens[index + 1] if index + 1 < len(tokens) else None
            diagnostics.append(_rejected(entry_id, token, value is not None))
            index += 2 if value is not None else 1
            continue
        if token.startswith(_UNSAFE_PREFIXES):
            diagnostics.append(_rejected(entry_id, _option_name(token), False))
            index += 1
            continue
        if token in _SAFE_PAIRED:
            if index + 1 >= len(tokens):
                diagnostics.append(_rejected(entry_id, token, False, code="clang.argument-missing-value"))
                index += 1
                continue
            value = tokens[index + 1]
            if token in _PATH_PAIRED:
                value = _normalize_path_value(value, context.directory or project_root)
            accepted.extend((token, value))
            index += 2
            continue
        if token.startswith(
            ("--target=", "--sysroot=", "-std=", "-D", "-U", "-isystem", "-iquote", "-idirafter", "-I")
        ) and len(token) > 2:
            accepted.append(_normalize_joined_path(token, context.directory or project_root))
            index += 1
            continue
        if token in _SAFE_EXACT or token in {"-m32", "-m64"} or token.startswith(_SAFE_TARGET_PREFIXES):
            accepted.append(token)
            index += 1
            continue
        if token.startswith("-"):
            diagnostics.append(_rejected(entry_id, _option_name(token), False))
            index += 1
            continue
        # Compiler inputs and driver operands are not passed to libclang's args list.
        index += 1
    return ClangArgumentResult(tuple(accepted), tuple(diagnostics))


def _normalize_path_value(value: str, directory: Path) -> str:
    path = Path(value)
    return str(path.resolve() if path.is_absolute() else (directory / path).resolve())


def _normalize_joined_path(token: str, directory: Path) -> str:
    for prefix in ("--sysroot=", "-isystem", "-iquote", "-idirafter", "-I"):
        if token.startswith(prefix):
            value = token[len(prefix) :]
            return f"{prefix}{_normalize_path_value(value, directory)}"
    return token


def _option_name(token: str) -> str:
    return token.split("=", 1)[0]


def _rejected(entry_id: str, option: str, had_value: bool, *, code: str = "clang.argument-rejected") -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="frontend.clang.arguments",
        severity=DiagnosticSeverity.WARNING,
        message=f"Rejected Clang parsing option: {option}",
        producer="clang-argument-policy",
        details={"compilationContextId": entry_id, "option": option, "removedPairedValue": had_value},
    )
