"""版本化 x86/RISC-V profile registry。"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from .canonical import semantic_digest
from .diagnostics import Diagnostic, diagnostic
from .protocol import SchemaRegistry


@dataclass(frozen=True, slots=True)
class TargetProfile:
    reference: str
    target_triple: str
    abi: str
    compiler_version: str
    fingerprint: str
    document: Mapping[str, Any]

    def summary(self) -> dict[str, str]:
        return {
            "profile": self.reference,
            "target_triple": self.target_triple,
            "abi": self.abi,
            "compiler_version": self.compiler_version,
            "fingerprint": self.fingerprint,
        }

    def core_rule_view(self) -> dict[str, Any]:
        """Return only normalized, provenance-bearing fields consumed by core rules."""
        floating_types = self.document.get("floating_types", {})
        long_double = (
            floating_types.get("long_double", {}) if isinstance(floating_types, Mapping) else {}
        )
        return {
            "profile": self.reference,
            "fingerprint": self.fingerprint,
            "long_double": dict(long_double) if isinstance(long_double, Mapping) else {},
            "evaluation": dict(self.document.get("evaluation", {})),
            "fma": dict(self.document.get("fma", {})),
            "environment": dict(self.document.get("environment", {})),
            "target_features": dict(self.document.get("target_features", {})),
        }


class ProfileRegistry:
    def __init__(
        self,
        documents: Iterable[Mapping[str, Any]] | None = None,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self._schemas = schema_registry or SchemaRegistry()
        loaded = list(documents) if documents is not None else self._builtin_documents()
        self._profiles: dict[str, TargetProfile] = {}
        failures: list[Diagnostic] = []
        for document in loaded:
            profile, errors = self._build(document)
            failures.extend(errors)
            if profile:
                if profile.reference in self._profiles:
                    failures.append(
                        diagnostic(
                            "duplicate_profile",
                            "profile_validation",
                            "Profile 标识重复。",
                            "Duplicate profile reference.",
                        )
                    )
                else:
                    self._profiles[profile.reference] = profile
        if failures:
            raise ProfileRegistryError(failures)

    @staticmethod
    def _builtin_documents() -> list[Mapping[str, Any]]:
        root = files("floating_point_precision_scanner").joinpath("profiles")
        return [
            json.loads(item.read_text(encoding="utf-8"))
            for item in sorted(root.iterdir(), key=lambda p: p.name)
            if item.name.endswith(".json")
        ]

    def _build(self, document: Mapping[str, Any]) -> tuple[TargetProfile | None, list[Diagnostic]]:
        errors = self._schemas.validate("profile", document)
        sources = document.get("sources")
        if not isinstance(sources, Mapping) or not sources:
            errors.append(
                diagnostic(
                    "profile_source_missing",
                    "profile_validation",
                    "Profile 缺少字段来源。",
                    "Profile field provenance is missing.",
                )
            )
        floating_types = document.get("floating_types")
        long_double = (
            floating_types.get("long_double") if isinstance(floating_types, Mapping) else None
        )
        if isinstance(long_double, Mapping):
            storage = long_double.get("storage_bits")
            precision = long_double.get("precision_bits")
            if isinstance(storage, int) and isinstance(precision, int) and precision > storage:
                errors.append(
                    diagnostic(
                        "profile_long_double_inconsistent",
                        "profile_validation",
                        "Profile 的 long double 精度超过存储位数。",
                        "The profile long double precision exceeds its storage width.",
                    )
                )
        if errors:
            return None, errors
        identifier = f"{document['profile_id']}@{document['profile_version']}"
        return TargetProfile(
            identifier,
            str(document["target_triple"]),
            str(document["abi"]),
            str(document["compiler"]["version"]),
            semantic_digest(document),
            dict(document),
        ), []

    def list(self) -> list[TargetProfile]:
        return [self._profiles[key] for key in sorted(self._profiles)]

    def get(self, reference: str) -> TargetProfile:
        try:
            return self._profiles[reference]
        except KeyError as exc:
            raise ProfileLookupError(reference) from exc

    def bind(self, source: str, target: str) -> tuple[TargetProfile, TargetProfile]:
        return self.get(source), self.get(target)

    @classmethod
    def from_directory(
        cls, directory: Path, schema_registry: SchemaRegistry | None = None
    ) -> ProfileRegistry:
        documents = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]
        return cls(documents, schema_registry)


class ProfileRegistryError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__("invalid_profile_registry")


class ProfileLookupError(KeyError):
    pass


def profile_context_diagnostic(
    profile: TargetProfile,
    *,
    target: str | None = None,
    abi: str | None = None,
    clang_version: str | None = None,
) -> Diagnostic | None:
    mismatches: list[str] = []
    if target and target != profile.target_triple:
        mismatches.append(f"target={target}")
    if abi and abi != profile.abi:
        mismatches.append(f"abi={abi}")
    if clang_version and clang_version != profile.compiler_version:
        mismatches.append(f"clang={clang_version}")
    if not mismatches:
        return None
    actual = ", ".join(mismatches)
    return diagnostic(
        "profile_context_conflict",
        "profile_binding",
        f"编译上下文与 Profile {profile.reference} 冲突：{actual}。",
        f"Compilation context conflicts with profile {profile.reference}: {actual}.",
        suggestion="选择匹配的固定版本 Profile 或修正编译参数。",
        suggestion_en="Select a matching pinned profile or correct the compile arguments.",
    )
