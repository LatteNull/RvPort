"""双语、可聚合且默认脱敏的诊断。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Diagnostic:
    diagnostic_code: str
    stage: str
    severity: str
    message: str
    message_en: str
    suggestion: str
    suggestion_en: str
    retryable: bool = False
    count: int = 1
    location: dict[str, Any] | None = None
    translation_unit_id: str | None = None

    def __post_init__(self) -> None:
        required = (self.message, self.message_en, self.suggestion, self.suggestion_en)
        if not all(item.strip() for item in required):
            raise ValueError("bilingual_diagnostic_fields_required")
        if self.count < 1:
            raise ValueError("diagnostic_count_must_be_positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_text(text: str, project_root: str | Path | None = None, limit: int = 2048) -> str:
    sanitized = text[:limit]
    sanitized = re.sub(
        r"(?i)(token|password|secret|api[_-]?key)\s*[=:]\s*\S+", r"\1=<redacted>", sanitized
    )
    if project_root:
        root = str(Path(project_root).resolve())
        sanitized = sanitized.replace(root, "<project_root>")
        sanitized = sanitized.replace(root.replace("\\", "/"), "<project_root>")
    sanitized = re.sub(
        r"(?<![\w.])(?:[A-Za-z]:[\\/]|/)(?:[^\s:'\"]+[\\/])+[^\s:'\"]+",
        "<external_path>",
        sanitized,
    )
    return sanitized


def aggregate_diagnostics(items: list[Diagnostic]) -> list[Diagnostic]:
    grouped: dict[tuple[str, str, str, str, str, bool], Diagnostic] = {}
    for item in items:
        key = (
            item.diagnostic_code,
            item.stage,
            item.severity,
            item.message,
            item.message_en,
            item.retryable,
        )
        prior = grouped.get(key)
        grouped[key] = item if prior is None else replace(prior, count=prior.count + item.count)
    return sorted(grouped.values(), key=lambda d: (d.stage, d.diagnostic_code, d.message_en))


def diagnostic(
    code: str,
    stage: str,
    zh: str,
    en: str,
    *,
    severity: str = "error",
    retryable: bool = False,
    suggestion: str = "请检查输入并重试。",
    suggestion_en: str = "Check the input and retry.",
    location: dict[str, Any] | None = None,
    translation_unit_id: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        code,
        stage,
        severity,
        zh,
        en,
        suggestion,
        suggestion_en,
        retryable,
        location=location,
        translation_unit_id=translation_unit_id,
    )
