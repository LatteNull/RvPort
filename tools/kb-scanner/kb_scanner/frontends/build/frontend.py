from __future__ import annotations

from pathlib import Path

from ...core import (
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    FrontendSnapshot,
    ScanContext,
    StageResult,
    WorkspaceSnapshot,
    merge_diagnostics,
)
from .adapters import AdapterResult, parse_m4, parse_machine_json, parse_rpm, parse_shell
from .autoconf.project import analyze_project
from .cmake.project import analyze_project as analyze_cmake
from .cmake.usage import bind_usage
from .make import parse_make
from .vocabulary import BuildInputKind, make_build_evidence, make_build_file_entity
from .workspace import build_input_kind


class BuildFrontend:
    __slots__ = ("_reader", "_max_bytes")

    def __init__(self, reader=None, max_bytes: int = 4 * 1024 * 1024) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._reader = reader or (lambda path: _read_text(path, max_bytes))
        self._max_bytes = max_bytes

    def analyze(self, context: ScanContext, workspace: WorkspaceSnapshot) -> StageResult[FrontendSnapshot]:
        entities = {}
        evidence = {}
        diagnostics: tuple[Diagnostic, ...] = ()
        partial = False
        autoconf = {}
        cmake = {}
        make = {}
        failed_inputs = set()
        total_bytes = 0
        for relative in sorted(workspace.files):
            if build_input_kind(relative) not in {BuildInputKind.SHELL, BuildInputKind.M4, BuildInputKind.CMAKE_SOURCE, BuildInputKind.MAKE}:
                continue
            try:
                path = workspace.root / relative
                path.resolve().relative_to(workspace.root.resolve())
                size = path.stat().st_size
                if size > self._max_bytes or total_bytes + size > 64 * 1024 * 1024:
                    raise ValueError("Build source input exceeds size budget")
                source = self._reader(path)
                actual = len(source.encode("utf-8"))
                if actual > self._max_bytes or total_bytes + actual > 64 * 1024 * 1024:
                    raise ValueError("Build source input changed beyond size budget")
                total_bytes += actual
                destination = make if build_input_kind(relative) is BuildInputKind.MAKE else cmake if build_input_kind(relative) is BuildInputKind.CMAKE_SOURCE else autoconf
                destination[relative] = source
            except (OSError, UnicodeError, ValueError, TypeError) as exc:
                failed_inputs.add(relative)
                diagnostics = merge_diagnostics(diagnostics, (_diagnostic("build-frontend.input-partial",
                    f"Build source input unavailable: {relative} ({type(exc).__name__})", relative),))
                partial = True
        autoconf_results = analyze_project(autoconf, context.target_arch)
        cmake_results = bind_usage(analyze_cmake(cmake, context.target_arch))
        for relative in sorted(workspace.files):
            input_kind = build_input_kind(relative)
            if input_kind is None:
                continue
            entity = make_build_file_entity(relative, input_kind, context.scanner_version)
            entities[entity.id] = entity
            if relative in failed_inputs:
                continue
            path = workspace.root / relative
            try:
                if relative in cmake_results:
                    result = cmake_results[relative]
                elif relative in make:
                    result = parse_make(make[relative], relative, context.target_arch, sources=make)
                elif relative in autoconf_results:
                    result = autoconf_results[relative]
                else:
                    if path.stat().st_size > self._max_bytes:
                        raise ValueError("input exceeds size budget")
                    source = self._reader(path)
                    result = self._parse(source, relative, input_kind, context.target_arch)
            except (OSError, UnicodeError, ValueError, TypeError) as exc:
                diagnostic = _diagnostic(
                    "build-frontend.input-partial",
                    f"Build input could not be fully analyzed: {relative} ({type(exc).__name__})",
                    relative,
                )
                diagnostics = merge_diagnostics(diagnostics, (diagnostic,))
                partial = True
                continue
            for message in result.diagnostics:
                diagnostics = merge_diagnostics(diagnostics, (_diagnostic("build-frontend.partial", message, relative),))
            partial = partial or result.partial
            producer = _producer(input_kind)
            for record in result.records:
                origin = (record.metadata or {}).get('sourcePath', relative)
                origin_entity = entity
                if origin != relative:
                    if origin not in make:
                        raise ValueError('Make origin is outside collected inputs')
                    origin_entity = make_build_file_entity(origin, input_kind, context.scanner_version)
                    entities[origin_entity.id] = origin_entity
                item = make_build_evidence(record, path=origin, subject_id=origin_entity.id, producer=producer, input_kind=input_kind)
                evidence[item.id] = item
        snapshot = FrontendSnapshot(
            entities=tuple(sorted(entities.values(), key=lambda item: (item.kind, item.name, item.id))),
            evidence=tuple(sorted(evidence.values(), key=lambda item: (item.location.start.path if item.location else "", item.location.start.line if item.location else 0, item.kind, item.id))),
        )
        return StageResult(snapshot, CompletionStatus.PARTIAL if partial else CompletionStatus.COMPLETE, diagnostics)

    @staticmethod
    def _parse(source: str, path: str, input_kind: BuildInputKind, target_arch: str) -> AdapterResult:
        if input_kind is BuildInputKind.MAKE:
            result = parse_make(source, path, target_arch)
            return AdapterResult(result.records, result.diagnostics, result.partial)
        if input_kind is BuildInputKind.SHELL:
            return parse_shell(source, path, target_arch)
        if input_kind is BuildInputKind.M4:
            return parse_m4(source, path, target_arch)
        if input_kind is BuildInputKind.RPM:
            return parse_rpm(source, path, target_arch)
        return parse_machine_json(source, path, input_kind.value, target_arch)


def _read_text(path: Path, max_bytes: int = 4 * 1024 * 1024) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read(max_bytes + 1)


def _producer(input_kind: BuildInputKind) -> str:
    return {
        BuildInputKind.MAKE: "tree-sitter-make+bounded-evaluator",
        BuildInputKind.SHELL: "tree-sitter-bash+bounded-autoconf",
        BuildInputKind.M4: "bounded-m4-recognizer",
        BuildInputKind.CMAKE: "cmake-file-api-reader",
        BuildInputKind.CMAKE_SOURCE: "tree-sitter-cmake+bounded-evaluator",
        BuildInputKind.MESON: "meson-introspection-reader",
        BuildInputKind.CTEST: "ctest-metadata-reader",
        BuildInputKind.COMPILATION_DATABASE: "compilation-database-build-reader",
        BuildInputKind.RPM: "bounded-rpm-parser",
    }[input_kind]


def _diagnostic(code: str, message: str, path: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="frontend.build",
        severity=DiagnosticSeverity.WARNING,
        message=message,
        producer="build-frontend",
        details={"path": path},
    )
