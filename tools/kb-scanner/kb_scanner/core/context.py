from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CompilationUnitContext:
    path: Path
    include_dirs: tuple[str, ...] = ()
    defines: tuple[tuple[str, str | None], ...] = ()
    language_standard: str | None = None
    raw_command: str | None = None
    tokens: tuple[str, ...] = ()
    entry_index: int = 0
    compiler: str | None = None
    directory: Path | None = None
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", self.path.resolve())
        object.__setattr__(self, "include_dirs", tuple(self.include_dirs))
        object.__setattr__(self, "defines", tuple(sorted(self.defines, key=lambda item: item[0])))
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.directory is not None:
            object.__setattr__(self, "directory", self.directory.resolve())


@dataclass(frozen=True, slots=True)
class ScanRequest:
    input_path: str
    rules_path: str
    output_path: str
    languages: tuple[str, ...] = ("c", "cpp")
    excludes: tuple[str, ...] = (".git", "build")
    exclude_paths: tuple[str, ...] = ()
    formats: tuple[str, ...] = ("json", "html")
    context_infer: str = "auto"
    target_arch: str = "riscv64"
    include_inactive_branches: bool = False
    include_comment_hints: bool = True
    compile_commands_path: str | None = None
    locale: str = "zh-CN"
    schema_version: str = "2.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "languages", tuple(self.languages))
        object.__setattr__(self, "excludes", tuple(self.excludes))
        object.__setattr__(self, "exclude_paths", tuple(self.exclude_paths))
        object.__setattr__(self, "formats", tuple(self.formats))
        if self.context_infer not in {"auto", "off"}:
            raise ValueError("context_infer must be auto or off")
        if self.schema_version not in {"1.0", "2.0"}:
            raise ValueError("schema_version must be 1.0 or 2.0")


@dataclass(frozen=True, slots=True)
class ScanContext:
    input_root: Path
    output_dir: Path
    rule_dir: Path
    languages: tuple[str, ...]
    excludes: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    formats: tuple[str, ...]
    context_infer: str
    target_arch: str
    include_inactive_branches: bool
    include_comment_hints: bool
    locale: str
    compile_commands_path: Path | None
    compile_contexts: tuple[CompilationUnitContext, ...]
    scan_mode: str
    rule_pack_id: str
    rule_pack_version: str
    knowledge_id: str
    scanner_name: str
    scanner_version: str
    knowledge_manifest_name: str = "knowledge-manifest.json"
    schema_version: str = "2.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_root", self.input_root.resolve())
        object.__setattr__(self, "output_dir", self.output_dir.resolve())
        object.__setattr__(self, "rule_dir", self.rule_dir.resolve())
        object.__setattr__(self, "languages", tuple(self.languages))
        object.__setattr__(self, "excludes", tuple(self.excludes))
        object.__setattr__(self, "exclude_paths", tuple(self.exclude_paths))
        object.__setattr__(self, "formats", tuple(self.formats))
        object.__setattr__(self, "compile_contexts", tuple(sorted(self.compile_contexts, key=lambda item: str(item.path))))
        if self.compile_commands_path is not None:
            object.__setattr__(self, "compile_commands_path", self.compile_commands_path.resolve())
        if not all((self.target_arch, self.rule_pack_id, self.rule_pack_version, self.knowledge_id, self.scanner_name, self.scanner_version, self.knowledge_manifest_name)):
            raise ValueError("scan context identity fields must not be empty")
        if self.schema_version not in {"1.0", "2.0"}:
            raise ValueError("schema_version must be 1.0 or 2.0")
