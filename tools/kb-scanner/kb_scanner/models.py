from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConditionFrame:
    kind: str
    expr: str
    macro: str | None
    line: int
    branch_group_id: str | None = None
    branch_role: str = "unknown"


@dataclass
class BranchInfo:
    kind: str
    expr: str
    line: int
    role: str


@dataclass
class MacroBranchGroup:
    id: str
    file: Path
    start_line: int
    branches: list[BranchInfo] = field(default_factory=list)


@dataclass
class IncludeFact:
    path: str
    file: Path
    line: int
    system: bool
    conditions: list[ConditionFrame] = field(default_factory=list)


@dataclass
class MacroDefinitionFact:
    name: str
    file: Path
    line: int
    params: list[str] | None
    body: str
    conditions: list[ConditionFrame] = field(default_factory=list)


@dataclass
class CallFact:
    name: str
    file: Path
    line: int
    text: str
    conditions: list[ConditionFrame] = field(default_factory=list)
    via_macro: str | None = None
    macro_definition_line: int | None = None


@dataclass
class TextFact:
    file: Path
    line: int
    text: str
    conditions: list[ConditionFrame] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileFacts:
    path: Path
    includes: list[IncludeFact] = field(default_factory=list)
    macros: list[MacroDefinitionFact] = field(default_factory=list)
    calls: list[CallFact] = field(default_factory=list)
    texts: list[TextFact] = field(default_factory=list)
    parse_mode: str = "source_context"
    diagnostics: list[str] = field(default_factory=list)
    branch_groups: dict[str, MacroBranchGroup] = field(default_factory=dict)


@dataclass
class CompileCommandContext:
    path: Path
    include_dirs: list[str] = field(default_factory=list)
    defines: dict[str, str | None] = field(default_factory=dict)
    language_standard: str | None = None
    raw_command: str | None = None
    tokens: list[str] = field(default_factory=list)
    entry_index: int = 0
    compiler: str | None = None
    directory: Path | None = None
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class ProjectFacts:
    root: Path
    files: list[FileFacts]
    scan_mode: str
    target_arch: str = "riscv64"
    include_inactive_branches: bool = False
    include_comment_hints: bool = True
    compile_commands_path: Path | None = None
    compile_contexts: dict[str, CompileCommandContext] = field(default_factory=dict)
    compile_reachable_files: set[str] = field(default_factory=set)
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class Rule:
    id: str
    language: str
    severity: str
    confidence: str
    match: dict[str, Any]
    message: dict[str, Any]
    capability: list[str] = field(default_factory=list)


@dataclass
class Finding:
    id: str
    rule_id: str
    severity: str
    confidence: str
    title: str
    title_en: str
    file: Path
    line: int
    column: int | None
    symbol: str | None
    reason: str
    reason_en: str
    suggestion: str
    suggestion_en: str
    snippet: str
    scan_mode: str
    finding_type: str = "issue"
    source_kind: str = "code"
    is_actionable: bool = True
    is_reference_source: bool = True
    is_blocking: bool = True
    arch_reachability: str = "unknown"
    branch_group_id: str | None = None
    branch_role: str | None = None
    compatible_sibling_branch: bool = False
    compatible_branch_kind: str | None = None
    build_context: dict[str, Any] = field(default_factory=dict)
    alternative_impl: dict[str, Any] = field(default_factory=dict)
    condition_macros: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)
