from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kb_scanner.core import ScanContext, SourceLocation, SourceSpan


ROOT = Path(__file__).resolve().parents[4]


def make_context(root: Path, **overrides: Any) -> ScanContext:
    values: dict[str, Any] = {
        "input_root": root,
        "output_dir": root / "out",
        "rule_dir": ROOT / "rulesets" / "riscv-porting",
        "languages": ("c", "cpp"),
        "excludes": (".git", "build"),
        "exclude_paths": (),
        "formats": ("json", "html"),
        "context_infer": "auto",
        "target_arch": "riscv64",
        "include_inactive_branches": False,
        "include_comment_hints": True,
        "locale": "zh-CN",
        "compile_commands_path": None,
        "compile_contexts": (),
        "scan_mode": "source_context",
        "rule_pack_id": "riscv-porting",
        "rule_pack_version": "1",
        "knowledge_id": "riscv-porting@1",
        "scanner_name": "kb-scanner",
        "scanner_version": "0.1.0",
    }
    values.update(overrides)
    return ScanContext(**values)


def span(path: str = "main.c", line: int = 1, start: int = 1, end: int = 4) -> SourceSpan:
    return SourceSpan(SourceLocation(path, line, start), SourceLocation(path, line, end))


def write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
