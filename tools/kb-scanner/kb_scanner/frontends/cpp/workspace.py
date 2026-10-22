from __future__ import annotations

from pathlib import Path, PurePosixPath

from ...core import (
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    ScanContext,
    StageResult,
    WorkspaceSnapshot,
)


C_SUFFIXES = frozenset({".c"})
CPP_SUFFIXES = frozenset({".cc", ".cpp", ".cxx"})
HEADER_SUFFIXES = frozenset({".h", ".hh", ".hpp", ".hxx", ".inc"})
SUPPORTED_SUFFIXES = C_SUFFIXES | CPP_SUFFIXES | HEADER_SUFFIXES


class CppWorkspaceCollector:
    __slots__ = ()

    def collect(self, context: ScanContext) -> StageResult[WorkspaceSnapshot]:
        source = context.input_root
        if not source.exists():
            diagnostic = _workspace_diagnostic("workspace.input-missing", "Input path does not exist", error=True)
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(diagnostic,))

        if source.is_file():
            root = source.parent.resolve()
            if not _is_supported(source, context.languages):
                diagnostic = _workspace_diagnostic(
                    "workspace.unsupported-input",
                    "Input file is not a supported C/C++ source or header",
                    error=True,
                )
                return StageResult(value=None, status=CompletionStatus.UNAVAILABLE, diagnostics=(diagnostic,))
            return StageResult(value=WorkspaceSnapshot(root=root, files=(source.name,)))

        root = source.resolve()
        files: list[str] = []
        diagnostics: list[Diagnostic] = []
        try:
            candidates = sorted((item for item in source.rglob("*") if item.is_file()), key=lambda item: item.as_posix())
        except OSError as exc:
            diagnostic = _workspace_diagnostic(
                "workspace.discovery-failed",
                f"Workspace discovery failed: {type(exc).__name__}",
                error=True,
            )
            return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(diagnostic,))

        for candidate in candidates:
            try:
                relative = candidate.relative_to(source).as_posix()
            except ValueError:
                continue
            if _is_excluded(relative, context.excludes, context.exclude_paths):
                continue
            if not _is_supported(candidate, context.languages):
                continue
            try:
                resolved = candidate.resolve()
            except OSError as exc:
                diagnostics.append(
                    _workspace_diagnostic(
                        "workspace.path-unreadable",
                        f"Skipped unreadable workspace path {relative}: {type(exc).__name__}",
                    )
                )
                continue
            if not resolved.is_relative_to(root):
                diagnostics.append(
                    _workspace_diagnostic(
                        "workspace.path-escape",
                        f"Skipped workspace path that resolves outside the project: {relative}",
                    )
                )
                continue
            files.append(PurePosixPath(relative).as_posix())

        status = CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE
        return StageResult(
            value=WorkspaceSnapshot(root=root, files=tuple(sorted(set(files)))),
            status=status,
            diagnostics=tuple(diagnostics),
        )


def language_candidates_for_path(path: str, languages: tuple[str, ...] = ("c", "cpp")) -> tuple[str, ...]:
    enabled = set(languages)
    suffix = Path(path).suffix.lower()
    if suffix in C_SUFFIXES:
        return ("c",) if "c" in enabled else ()
    if suffix in CPP_SUFFIXES:
        return ("cpp",) if "cpp" in enabled else ()
    if suffix in HEADER_SUFFIXES:
        return tuple(item for item in ("c", "cpp") if item in enabled)
    return ()


def _is_supported(path: Path, languages: tuple[str, ...]) -> bool:
    return bool(language_candidates_for_path(path.name, languages))


def _is_excluded(relative_path: str, excludes: tuple[str, ...], exclude_paths: tuple[str, ...]) -> bool:
    relative = PurePosixPath(relative_path)
    directory_parts = set(relative.parts[:-1])
    if any(name in directory_parts for name in excludes):
        return True
    normalized = relative.as_posix()
    for raw in exclude_paths:
        excluded = PurePosixPath(str(raw).replace("\\", "/").strip("/")).as_posix()
        if excluded in {"", "."}:
            continue
        if normalized == excluded or normalized.startswith(f"{excluded}/"):
            return True
    return False


def _workspace_diagnostic(code: str, message: str, *, error: bool = False) -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="workspace",
        severity=DiagnosticSeverity.ERROR if error else DiagnosticSeverity.WARNING,
        message=message,
        producer="cpp-workspace-collector",
        affects_exit_code=error,
    )
