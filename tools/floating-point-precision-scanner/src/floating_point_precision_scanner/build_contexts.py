"""不可变 source/target 构建环境 overlay。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .canonical import semantic_digest
from .diagnostics import Diagnostic, diagnostic


@dataclass(frozen=True, slots=True)
class BuildContext:
    context_id: str
    base_profile_fingerprint: str
    target_triple: str
    abi: str
    fingerprint: str
    document: Mapping[str, Any]

    def summary(self) -> dict[str, str]:
        return {
            "context_id": self.context_id,
            "base_profile_fingerprint": self.base_profile_fingerprint,
            "target_triple": self.target_triple,
            "abi": self.abi,
            "fingerprint": self.fingerprint,
        }

    def capability(self, field: str) -> Mapping[str, Any] | None:
        value = self.document.get(field)
        if not isinstance(value, Mapping) or value.get("status") != "known":
            return None
        payload = value.get("value")
        return payload if isinstance(payload, Mapping) else None


def build_context(
    document: Mapping[str, Any],
    *,
    profile_fingerprint: str,
    target_triple: str,
    abi: str,
) -> tuple[BuildContext | None, list[Diagnostic]]:
    mismatches: list[str] = []
    if document.get("base_profile_fingerprint") != profile_fingerprint:
        mismatches.append("base_profile_fingerprint")
    if document.get("target_triple") != target_triple:
        mismatches.append("target_triple")
    if document.get("abi") != abi:
        mismatches.append("abi")
    if mismatches:
        return None, [
            diagnostic(
                "build_context_mismatch",
                "build_context_validation",
                "构建环境与绑定的目标 Profile 不一致。",
                "The build context does not match its bound target profile.",
                suggestion=", ".join(mismatches),
                suggestion_en=", ".join(mismatches),
            )
        ]
    sources = document.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        return None, [
            diagnostic(
                "build_context_source_missing",
                "build_context_validation",
                "构建环境缺少字段来源。",
                "Build-context field provenance is missing.",
            )
        ]
    semantic = dict(document)
    semantic.pop("materialization_root", None)
    return (
        BuildContext(
            context_id=str(document["context_id"]),
            base_profile_fingerprint=profile_fingerprint,
            target_triple=target_triple,
            abi=abi,
            fingerprint=semantic_digest(semantic),
            document=semantic,
        ),
        [],
    )
