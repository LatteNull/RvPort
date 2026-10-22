from __future__ import annotations

from pathlib import Path

from kb_scanner.core import KnowledgeEntry, KnowledgeSnapshot, KnowledgeSource, ScanContext, stable_id


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "build-selection" / "project"


def context(root: Path = FIXTURE, *, target_arch: str = "riscv64", excludes: tuple[str, ...] = ()) -> ScanContext:
    return ScanContext(
        input_root=root,
        output_dir=root / "out",
        rule_dir=ROOT / "rulesets" / "riscv-porting",
        languages=("c", "cpp"),
        excludes=excludes,
        exclude_paths=(),
        formats=("json", "html"),
        context_infer="auto",
        target_arch=target_arch,
        include_inactive_branches=False,
        include_comment_hints=True,
        locale="zh-CN",
        compile_commands_path=root / "compile_commands.json" if root.is_dir() else None,
        compile_contexts=(),
        scan_mode="source_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="test@1",
        scanner_name="kb-scanner",
        scanner_version="1",
    )


def flag_knowledge(*flags: str) -> KnowledgeSnapshot:
    source_id = stable_id("knowledge_source", "test")
    source = KnowledgeSource(source_id, "test", "generated", "facts.json", "0" * 64)
    entries = tuple(
        KnowledgeEntry(stable_id("knowledge_entry", "compilerFlags", flag), "compilerFlags", "x86", flag, (source_id,))
        for flag in flags
    )
    return KnowledgeSnapshot(stable_id("knowledge", flags), "1", (source,), entries)
