from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .identity import canonicalize_fact_value
from .schema import GeneratedFactV2Model, SourceDescriptorModel


_BINUTILS_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_.()]*$")
_LLVM_REGISTER = re.compile(r'X86Reg(?:WithSubRegs)?<"([^"]+)"')
_LLVM_FEATURE = re.compile(r'SubtargetFeature<"([^"]+)"')
_LLVM_CPU = re.compile(r'(?:Proc|ProcModel)<"([^"]+)"')
_LLVM_ASM_STRING = re.compile(r'"([a-z][a-z0-9.]*)(?:\{[^"\n]*\})?[^"\n]*(?:\\t|\$)[^"\n]*"')
_LLVM_META_MNEMONICS = frozenset({"dq", "j", "pd", "ps", "sd", "set", "x", "y", "z"})
_GCC_ALIAS = re.compile(r'\{"([^"]+)",\s*PROCESSOR_[A-Z0-9_]+')
_GCC_FEATURE = re.compile(r'ISA_NAMES_TABLE_ENTRY\("([^"]+)"')


@dataclass(frozen=True, slots=True)
class ExtractionDiagnostic:
    code: str
    message: str
    logical_path: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    facts: tuple[GeneratedFactV2Model, ...] = ()
    input_paths: tuple[str, ...] = ()
    input_sha256: tuple[str, ...] = ()
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return bool(self.facts) and not self.diagnostics


class ReadOnlySource:
    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def read(self, logical_path: str) -> tuple[str, str] | ExtractionDiagnostic:
        normalized = logical_path.replace("\\", "/")
        path = (self._root / normalized).resolve()
        if path == self._root or not path.is_relative_to(self._root):
            return ExtractionDiagnostic("extractor.path-escape", "Source path resolves outside the declared root", normalized)
        try:
            content = path.read_bytes()
        except OSError as exc:
            return ExtractionDiagnostic("extractor.source-unreadable", f"Source input is unreadable: {type(exc).__name__}", normalized)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return ExtractionDiagnostic("extractor.source-encoding", "Source input is not UTF-8", normalized)
        return text, hashlib.sha256(content).hexdigest()


def extract_binutils(root: Path, opcode_path: str, register_path: str) -> ExtractionResult:
    loaded = _load_all(ReadOnlySource(root), (opcode_path, register_path))
    if isinstance(loaded, ExtractionResult):
        return loaded
    texts, hashes = loaded
    instructions = _binutils_column(texts[0])
    registers = _binutils_column(texts[1])
    if not instructions or not registers:
        return _unsupported((opcode_path, register_path), "Binutils tables contain no recognized x86 records")
    facts = _facts("assemblyInstructions", instructions, "x86-only") + _facts("registerNames", registers, "x86-only")
    return ExtractionResult(_ordered(facts), (opcode_path, register_path), hashes)


def extract_llvm(
    root: Path, register_path: str, target_path: str, instruction_paths: tuple[str, ...] = (),
) -> ExtractionResult:
    paths = (register_path, target_path, *instruction_paths)
    loaded = _load_all(ReadOnlySource(root), paths)
    if isinstance(loaded, ExtractionResult):
        return loaded
    texts, hashes = loaded
    registers = set(_LLVM_REGISTER.findall(texts[0]))
    features = set(_LLVM_FEATURE.findall(texts[1]))
    cpus = set(_LLVM_CPU.findall(texts[1]))
    if not registers or not features or not cpus:
        return _unsupported((register_path, target_path), "LLVM X86 definitions do not match the supported structure")
    facts = (
        _facts("registerNames", registers, "x86-only")
        + _facts("targetFeatures", features, "x86-toolchain")
        + _facts("architectureAliases", cpus, "x86-toolchain")
    )
    if instruction_paths:
        instructions = {
            value
            for text in texts[2:]
            for value in _LLVM_ASM_STRING.findall(text)
            if len(value) > 1 and value not in _LLVM_META_MNEMONICS
        }
        if not instructions:
            return _unsupported(paths, "LLVM instruction definitions contain no recognized assembly strings")
        facts += _facts("assemblyInstructions", instructions, "x86-only")
    return ExtractionResult(_ordered(facts), paths, hashes)


def extract_gcc(root: Path, aliases_path: str, features_path: str) -> ExtractionResult:
    loaded = _load_all(ReadOnlySource(root), (aliases_path, features_path))
    if isinstance(loaded, ExtractionResult):
        return loaded
    texts, hashes = loaded
    aliases = set(_GCC_ALIAS.findall(texts[0]))
    features = set(_GCC_FEATURE.findall(texts[1]))
    if not aliases or not features:
        return _unsupported((aliases_path, features_path), "GCC i386 definitions do not match the supported structure")
    facts = _facts("architectureAliases", aliases, "x86-toolchain") + _facts("targetFeatures", features, "x86-toolchain")
    return ExtractionResult(_ordered(facts), (aliases_path, features_path), hashes)


def with_descriptor(descriptor: SourceDescriptorModel, result: ExtractionResult) -> SourceDescriptorModel:
    if not result.succeeded:
        raise ValueError("cannot attach an unsuccessful extraction")
    return descriptor.model_copy(update={"inputPaths": result.input_paths, "inputSha256": result.input_sha256})


def _load_all(source: ReadOnlySource, paths: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]] | ExtractionResult:
    texts: list[str] = []
    hashes: list[str] = []
    diagnostics: list[ExtractionDiagnostic] = []
    for path in paths:
        loaded = source.read(path)
        if isinstance(loaded, ExtractionDiagnostic):
            diagnostics.append(loaded)
        else:
            text, digest = loaded
            texts.append(text)
            hashes.append(digest)
    if diagnostics:
        return ExtractionResult(input_paths=paths, diagnostics=tuple(diagnostics))
    return tuple(texts), tuple(hashes)


def _binutils_column(text: str) -> set[str]:
    values: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "//", ";")) or "," not in line:
            continue
        token = line.split(",", 1)[0].strip()
        if _BINUTILS_TOKEN.fullmatch(token):
            values.add(token)
    return values


def _facts(kind: str, values: set[str], scope: str) -> tuple[GeneratedFactV2Model, ...]:
    return tuple(
        GeneratedFactV2Model(
            factKind=kind,
            architectureFamily="x86",
            canonicalValue=canonicalize_fact_value(kind, value),
            semanticScope=scope,
        )
        for value in values
    )


def _ordered(facts: tuple[GeneratedFactV2Model, ...]) -> tuple[GeneratedFactV2Model, ...]:
    unique = {(item.factKind, item.architectureFamily, item.canonicalValue): item for item in facts}
    return tuple(unique[key] for key in sorted(unique))


def _unsupported(paths: tuple[str, ...], message: str) -> ExtractionResult:
    return ExtractionResult(
        input_paths=paths,
        diagnostics=(ExtractionDiagnostic("extractor.unsupported-structure", message, paths[0]),),
    )
