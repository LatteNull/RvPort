"""确定性 JSON、摘要和稳定身份。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def canonical_json(value: Any) -> str:
    """返回 UTF-8 语义稳定的 JSON 子集。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def semantic_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def stable_id(kind: str, payload: Mapping[str, Any]) -> str:
    return semantic_digest({"kind": kind, "payload": payload})


def normalize_repo_path(path: str | Path, project_root: str | Path) -> str:
    root = Path(project_root).resolve()
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = root / resolved
    resolved = resolved.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path_outside_project_root") from exc
    return relative.as_posix()


def stable_sorted(values: Iterable[T], key: Callable[[T], Any]) -> list[T]:
    return sorted(values, key=key)


def finding_id(
    rule_code: str, rule_version: str, path: str, line: int, payload: Mapping[str, Any]
) -> str:
    return stable_id(
        "finding",
        {
            "rule_code": rule_code,
            "rule_version": rule_version,
            "path": path,
            "line": line,
            "semantic": payload,
        },
    )
