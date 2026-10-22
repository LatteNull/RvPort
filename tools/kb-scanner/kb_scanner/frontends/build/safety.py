from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandDisposition:
    recognized: bool
    value: str | None
    reason: str


_UNAME_FORMS = (
    re.compile(r"^uname\s+-m$"),
    re.compile(r"^\$\(\s*uname\s+-m\s*\)$"),
    re.compile(r"^`\s*uname\s+-m\s*`$"),
    re.compile(r"^\$\(\s*shell\s+uname\s+-m\s*\)$"),
)


UNSAFE_PATTERNS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "make": (
        ("shell-function", re.compile(r"\$\(\s*shell\b", re.IGNORECASE)),
        ("shell-assignment", re.compile(r"(?m)^\s*[^#\n]+?\s*!=\s*.+$")),
        ("eval-function", re.compile(r"\$\(\s*eval\b", re.IGNORECASE)),
        ("dynamic-function", re.compile(r"\$\(\s*(?:call|foreach|wildcard)\b", re.IGNORECASE)),
    ),
    "m4": (
        ("m4-syscmd", re.compile(r"\b(?:m4_)?syscmd\s*\(", re.IGNORECASE)),
        ("m4-esyscmd", re.compile(r"\b(?:m4_)?esyscmd\s*\(", re.IGNORECASE)),
        ("m4-include", re.compile(r"\b(?:m4_)?include\s*\(", re.IGNORECASE)),
    ),
    "cmake": (("cmake-execute-process", re.compile(r"\bexecute_process\s*\(", re.IGNORECASE)),),
    "rpm": (
        ("rpm-shell-expansion", re.compile(r"%\(")),
        ("rpm-lua-expansion", re.compile(r"%\{\s*lua\s*:", re.IGNORECASE)),
        ("rpm-include", re.compile(r"(?m)^\s*%include\b", re.IGNORECASE)),
    ),
}


def normalize_target_arch(target_arch: str) -> str:
    value = target_arch.strip().lower().replace("_", "-")
    if value.startswith("riscv32") or value in {"rv32", "risc-v32"}:
        return "riscv32"
    if value.startswith("riscv64") or value in {"riscv", "rv64", "risc-v", "risc-v64"}:
        return "riscv64"
    raise ValueError("build selection only supports RISC-V target architectures")


def symbolic_uname(command: str, target_arch: str) -> CommandDisposition:
    candidate = " ".join(command.strip().split())
    if any(pattern.fullmatch(candidate) for pattern in _UNAME_FORMS):
        return CommandDisposition(True, normalize_target_arch(target_arch), "symbolic-uname-m")
    return CommandDisposition(False, None, "unsupported-command-shape")


def unsafe_constructs(source: str, input_kind: str) -> tuple[tuple[str, int, str], ...]:
    found: list[tuple[str, int, str]] = []
    lines = source.splitlines()
    for name, pattern in UNSAFE_PATTERNS.get(input_kind, ()):
        for match in pattern.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            text = lines[line - 1].strip() if line <= len(lines) else ""
            if input_kind == "make" and name in {"shell-function", "shell-assignment"}:
                command = _make_command(text, name)
                if command is not None and symbolic_uname(command, "riscv64").recognized:
                    continue
            found.append((name, line, text))
    return tuple(sorted(found, key=lambda item: (item[1], item[0], item[2])))


def _make_command(line: str, construct: str) -> str | None:
    if construct == "shell-function":
        match = re.search(r"\$\(\s*shell\s+([^)]*)\)", line, re.IGNORECASE)
        return match.group(1).strip() if match else None
    if construct == "shell-assignment":
        return line.split("!=", 1)[1].strip() if "!=" in line else None
    return None
