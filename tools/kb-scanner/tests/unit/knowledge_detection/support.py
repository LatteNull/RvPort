from __future__ import annotations

from pathlib import Path

from kb_scanner.core import (
    CompilationUnitContext,
    Entity,
    Evidence,
    ScanContext,
    SourceLocation,
    SourceSpan,
    stable_id,
)


def make_context(
    root: Path,
    *,
    rule_dir: Path | None = None,
    compile_contexts: tuple[CompilationUnitContext, ...] = (),
) -> ScanContext:
    return ScanContext(
        input_root=root,
        output_dir=root / "out",
        rule_dir=rule_dir or root / "rules",
        languages=("c", "cpp"),
        excludes=(".git", "build"),
        exclude_paths=(),
        formats=("json", "html"),
        context_infer="auto",
        target_arch="riscv64",
        include_inactive_branches=False,
        include_comment_hints=True,
        locale="zh-CN",
        compile_commands_path=None,
        compile_contexts=compile_contexts,
        scan_mode="source_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="riscv-porting@1",
        scanner_name="kb-scanner",
        scanner_version="0.1.0",
    )


def make_entity(path: str = "main.c") -> Entity:
    return Entity(stable_id("source_file", path), "source_file", path)


def make_span(path: str = "main.c", line: int = 1) -> SourceSpan:
    return SourceSpan(SourceLocation(path, line, 1), SourceLocation(path, line, 8))


def make_evidence(
    entity: Entity,
    kind: str,
    value: object,
    *,
    producer: str = "test",
    line: int = 1,
    metadata: dict | None = None,
) -> Evidence:
    span = make_span(entity.name, line)
    return Evidence(
        stable_id("evidence", kind, entity.id, value, span, producer),
        kind,
        entity.id,
        value,
        producer,
        "unit",
        "high",
        span,
        metadata=metadata,
    )
