from __future__ import annotations

from pathlib import Path

from kb_scanner.core import (
    Entity,
    Evidence,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    ScanContext,
    SourceLocation,
    SourceSpan,
    stable_id,
)


def context(root: Path) -> ScanContext:
    return ScanContext(
        input_root=root,
        output_dir=root / "out",
        rule_dir=root / "rules",
        languages=("c", "cpp"),
        excludes=(),
        exclude_paths=(),
        formats=("json",),
        context_infer="auto",
        target_arch="riscv64",
        include_inactive_branches=False,
        include_comment_hints=True,
        locale="zh-CN",
        compile_commands_path=None,
        compile_contexts=(),
        scan_mode="source_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="knowledge@1",
        scanner_name="kb-scanner",
        scanner_version="1",
    )


def file(path: str) -> Entity:
    return Entity(stable_id("source_file", path), "source_file", path)


def span(path: str, start_line: int, end_line: int | None = None, start_column: int = 1, end_column: int = 20) -> SourceSpan:
    return SourceSpan(
        SourceLocation(path, start_line, start_column),
        SourceLocation(path, end_line or start_line, end_column),
    )


def evidence(
    subject: Entity,
    kind: str,
    value: str,
    line: int,
    *,
    end_line: int | None = None,
    metadata: dict[str, object] | None = None,
) -> Evidence:
    location = span(subject.name, line, end_line)
    return Evidence(
        stable_id("evidence", kind, subject.id, value, location),
        kind,
        subject.id,
        value,
        "unit",
        "syntax",
        "high",
        location,
        metadata=metadata,
    )


def snapshot(*items: Entity, evidence_items: tuple[Evidence, ...] = ()) -> NormalizedSnapshot:
    return NormalizedSnapshot(tuple(items), evidence_items, ())


def knowledge() -> KnowledgeSnapshot:
    return KnowledgeSnapshot(stable_id("knowledge"), "1")
