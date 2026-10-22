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
    normalize_project_path,
)
from .clang_adapter import ClangCppAdapter
from .tree_sitter_adapter import TreeSitterCppAdapter
from .vocabulary import entity_sort_key, evidence_sort_key, make_source_file_entity
from .workspace import language_candidates_for_path
from .usage_inventory import cap_records
from .test_inventory import cap_records as cap_test_records


class CppFrontend:
    __slots__ = ("_tree_sitter", "_clang", "_usage_record_limit")

    def __init__(
        self,
        tree_sitter: TreeSitterCppAdapter | None = None,
        clang: ClangCppAdapter | None = None,
        *, usage_record_limit: int = 100000,
    ) -> None:
        self._tree_sitter = tree_sitter or TreeSitterCppAdapter()
        self._clang = clang
        if type(usage_record_limit) is not int or not 0 <= usage_record_limit <= 100000:
            raise ValueError("usage record limit must be between 0 and 100000")
        self._usage_record_limit = usage_record_limit

    def analyze(self, context: ScanContext, workspace: WorkspaceSnapshot, *, usage_selector=None) -> StageResult[FrontendSnapshot]:
        entities_by_path = {
            relative_path: make_source_file_entity(
                relative_path,
                language_candidates_for_path(relative_path, context.languages),
                context.scanner_version,
            )
            for relative_path in workspace.files
        }
        evidence_by_id = {}
        diagnostics: tuple[Diagnostic, ...] = ()
        overall_status = CompletionStatus.COMPLETE
        usage_remaining = self._usage_record_limit
        test_remaining = 100000

        for relative_path in workspace.files:
            result = self._tree_sitter.analyze_file(
                context,
                workspace.root,
                relative_path,
                entities_by_path[relative_path],
                **({"usage_selector": usage_selector} if usage_selector is not None else {}),
                **({"test_record_limit": test_remaining} if test_remaining < 10000 else {}),
            )
            diagnostics = merge_diagnostics(diagnostics, result.diagnostics)
            if result.status is CompletionStatus.FAILED or result.value is None:
                return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=diagnostics)
            if result.status is CompletionStatus.PARTIAL:
                overall_status = CompletionStatus.PARTIAL
            for item in result.value:
                item, usage_remaining = cap_records(item, usage_remaining)
                item, test_remaining = cap_test_records(item, test_remaining)
                evidence_by_id[item.id] = item

        if self._clang is not None:
            function_targets = {}
            for item in evidence_by_id.values():
                if item.kind == "function_declaration" and item.location is not None:
                    location = item.location.start
                    function_targets.setdefault(location.path, set()).add((location.line, location.column))
            for unit in context.compile_contexts:
                relative_path = _unit_relative_path(unit.path, workspace.root)
                if relative_path is None or relative_path not in entities_by_path:
                    continue
                options = {"function_targets": function_targets} if function_targets else {}
                result = self._clang.enrich(context, workspace, unit, entities_by_path, **options)
                diagnostics = merge_diagnostics(diagnostics, result.diagnostics)
                if result.status in {CompletionStatus.PARTIAL, CompletionStatus.UNAVAILABLE, CompletionStatus.FAILED}:
                    overall_status = CompletionStatus.PARTIAL
                if result.value is not None:
                    for item in result.value:
                        evidence_by_id[item.id] = item

        entity_ids = {item.id for item in entities_by_path.values()}
        invalid = [item for item in evidence_by_id.values() if item.subject_id not in entity_ids]
        if invalid:
            diagnostic = Diagnostic(
                code="frontend.invalid-subject-reference",
                stage="frontend",
                severity=DiagnosticSeverity.FATAL,
                message="Frontend produced Evidence with an unknown subject Entity",
                producer="cpp-frontend",
                details={"invalidReferenceCount": len(invalid)},
                affects_exit_code=True,
            )
            return StageResult(
                value=None,
                status=CompletionStatus.FAILED,
                diagnostics=merge_diagnostics(diagnostics, (diagnostic,)),
            )

        snapshot = FrontendSnapshot(
            entities=tuple(sorted(entities_by_path.values(), key=entity_sort_key)),
            evidence=tuple(sorted(evidence_by_id.values(), key=evidence_sort_key)),
        )
        return StageResult(value=snapshot, status=overall_status, diagnostics=diagnostics)


def _unit_relative_path(path: Path, workspace_root: Path) -> str | None:
    try:
        return normalize_project_path(path, workspace_root)
    except ValueError:
        return None
