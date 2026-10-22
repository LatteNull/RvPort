from __future__ import annotations

from pathlib import Path, PurePosixPath

from ...core import CompletionStatus, Diagnostic, DiagnosticSeverity, ScanContext, StageResult, WorkspaceSnapshot
from ..cpp.workspace import CppWorkspaceCollector
from .vocabulary import BuildInputKind


_MAKE_NAMES = frozenset({"makefile", "gnumakefile", "bsdmakefile"})


def build_input_kind(path: str) -> BuildInputKind | None:
    normalized = path.replace("\\", "/")
    name = PurePosixPath(normalized).name
    lowered = name.lower()
    parts = {part.lower() for part in PurePosixPath(normalized).parts}
    if lowered in _MAKE_NAMES or lowered.endswith(".mk") or lowered.startswith("makefile."):
        return BuildInputKind.MAKE
    if lowered in {"configure", "config.sub", "config.guess"}:
        return BuildInputKind.SHELL
    if lowered == "configure.ac" or lowered.endswith(".m4"):
        return BuildInputKind.M4
    if lowered == "compile_commands.json":
        return BuildInputKind.COMPILATION_DATABASE
    if lowered == "ctesttestfile.cmake" or lowered.startswith("ctest") and lowered.endswith(".json"):
        return BuildInputKind.CTEST
    if "meson-info" in parts and lowered.startswith("intro-") and lowered.endswith(".json"):
        return BuildInputKind.MESON
    if ".cmake" in parts and "reply" in parts and lowered.endswith(".json"):
        return BuildInputKind.CMAKE
    if lowered == "cmakelists.txt" or lowered.endswith(".cmake"):
        return BuildInputKind.CMAKE_SOURCE
    if lowered.endswith(".spec"):
        return BuildInputKind.RPM
    return None


def is_build_input(path: str) -> bool:
    return build_input_kind(path) is not None


class ProjectWorkspaceCollector:
    __slots__ = ("_cpp",)

    def __init__(self, cpp: CppWorkspaceCollector | None = None) -> None:
        self._cpp = cpp or CppWorkspaceCollector()

    def collect(self, context: ScanContext) -> StageResult[WorkspaceSnapshot]:
        source = context.input_root
        if not source.exists():
            return _failed("workspace.input-missing", "Input path does not exist")
        if source.is_file():
            kind = build_input_kind(source.name)
            if kind is not None:
                return StageResult(WorkspaceSnapshot(source.parent.resolve(), (source.name,)))
            return self._cpp.collect(context)

        cpp_result = self._cpp.collect(context)
        if cpp_result.status is CompletionStatus.FAILED or cpp_result.value is None:
            return cpp_result
        root = source.resolve()
        files = set(cpp_result.value.files)
        diagnostics = list(cpp_result.diagnostics)
        try:
            candidates = sorted((item for item in source.rglob("*") if item.is_file()), key=lambda item: item.as_posix())
        except OSError as exc:
            return _failed("workspace.discovery-failed", f"Workspace discovery failed: {type(exc).__name__}")
        for candidate in candidates:
            relative = candidate.relative_to(source).as_posix()
            if _excluded(relative, context.excludes, context.exclude_paths) or not is_build_input(relative):
                continue
            try:
                resolved = candidate.resolve()
            except OSError as exc:
                diagnostics.append(_warning("workspace.build-path-unreadable", f"Skipped unreadable build path {relative}: {type(exc).__name__}"))
                continue
            if not resolved.is_relative_to(root):
                diagnostics.append(_warning("workspace.build-path-escape", f"Skipped build path outside workspace: {relative}"))
                continue
            files.add(PurePosixPath(relative).as_posix())
        status = CompletionStatus.PARTIAL if diagnostics else cpp_result.status
        return StageResult(WorkspaceSnapshot(root, tuple(sorted(files))), status, tuple(diagnostics))


def _excluded(relative_path: str, excludes: tuple[str, ...], exclude_paths: tuple[str, ...]) -> bool:
    relative = PurePosixPath(relative_path)
    if any(name in set(relative.parts[:-1]) for name in excludes):
        return True
    normalized = relative.as_posix()
    return any(
        normalized == raw.replace("\\", "/").strip("/")
        or normalized.startswith(raw.replace("\\", "/").strip("/") + "/")
        for raw in exclude_paths
        if raw.replace("\\", "/").strip("/")
    )


def _warning(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, "workspace", DiagnosticSeverity.WARNING, message, producer="project-workspace-collector")


def _failed(code: str, message: str) -> StageResult[WorkspaceSnapshot]:
    diagnostic = Diagnostic(code, "workspace", DiagnosticSeverity.ERROR, message, producer="project-workspace-collector", affects_exit_code=True)
    return StageResult(None, CompletionStatus.FAILED, (diagnostic,))
