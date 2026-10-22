from __future__ import annotations

import argparse
from pathlib import Path

from .. import __version__
from ..bundle import BundleError, load_bundle_descriptor
from ..core import CompletionStatus, Diagnostic, DiagnosticSeverity, ScanContext, ScanRequest, StageResult
from ..frontends.cpp.compilation_database import CompilationDatabaseReader


def scan_request_from_namespace(args: argparse.Namespace) -> ScanRequest:
    return ScanRequest(
        input_path=args.input,
        rules_path=args.rules,
        output_path=args.output,
        languages=_split_csv(args.language),
        excludes=_split_csv(args.exclude),
        exclude_paths=tuple(item.strip() for item in args.exclude_path if item.strip()),
        formats=_split_csv(args.format),
        context_infer=args.context_infer,
        target_arch=args.target_arch,
        include_inactive_branches=args.include_inactive_branches,
        include_comment_hints=not args.no_comment_hints,
        compile_commands_path=args.compile_commands,
        locale=args.locale,
        schema_version=getattr(args, "schema_version", "2.0"),
    )


class StagedContextFactory:
    __slots__ = ("_database",)

    def __init__(self, database: CompilationDatabaseReader | None = None) -> None:
        self._database = database or CompilationDatabaseReader()

    def build(self, request: ScanRequest) -> StageResult[ScanContext]:
        root = Path(request.input_path).resolve()
        rule_dir = Path(request.rules_path).resolve()
        output_dir = Path(request.output_path).resolve()
        if not root.is_dir():
            return _failed("context.input-invalid", "Input root must be an existing directory")
        try:
            bundle = load_bundle_descriptor(rule_dir)
        except BundleError as exc:
            return _failed("context.bundle-invalid", str(exc))
        candidate = Path(request.compile_commands_path).resolve() if request.compile_commands_path else root / "compile_commands.json"
        database = self._database.read(candidate if candidate.exists() else None, root)
        contexts = database.value or ()
        diagnostics = tuple(
            item for item in database.diagnostics if item.code != "compilation-database.missing"
        )
        scan_mode = "source_context_with_compile_database" if contexts else "source_context"
        if request.context_infer == "off" and not contexts:
            scan_mode = "syntax_scan"
        status = CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE
        return StageResult(
            ScanContext(
                input_root=root,
                output_dir=output_dir,
                rule_dir=rule_dir,
                languages=request.languages,
                excludes=request.excludes,
                exclude_paths=request.exclude_paths,
                formats=request.formats,
                context_infer=request.context_infer,
                target_arch=request.target_arch,
                include_inactive_branches=request.include_inactive_branches,
                include_comment_hints=request.include_comment_hints,
                locale=request.locale,
                compile_commands_path=candidate if candidate.exists() else None,
                compile_contexts=contexts,
                scan_mode=scan_mode,
                rule_pack_id=bundle.rule_pack_id,
                rule_pack_version=bundle.rule_pack_version,
                knowledge_id=bundle.identity,
                scanner_name="kb-scanner",
                scanner_version=__version__,
                knowledge_manifest_name=bundle.knowledge_manifest_path.relative_to(rule_dir).as_posix(),
                schema_version=request.schema_version,
            ),
            status,
            diagnostics,
        )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _failed(code: str, message: str) -> StageResult[ScanContext]:
    return StageResult(
        None,
        CompletionStatus.FAILED,
        (Diagnostic(code, "context", DiagnosticSeverity.ERROR, message, producer="staged-context-factory", affects_exit_code=True),),
    )
