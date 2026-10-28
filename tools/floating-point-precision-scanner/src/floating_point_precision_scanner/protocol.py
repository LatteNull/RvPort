"""版本化协议加载、校验与不可变请求模型。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from .cache import CACHE_MODES, CacheConfig
from .diagnostics import Diagnostic, diagnostic
from .result_v2 import (
    EXTENSION_ANALYSIS,
    EXTENSION_ARTIFACTS,
    EXTENSION_PROFILES,
    EXTENSION_RUNTIME,
    EXTENSION_SUPPRESSIONS,
    validate_result_invariants,
)
from .rules import normalize_rule_selection
from .suppression import Suppression, parse_suppressions

SCHEMA_PATHS = {
    "request": "schemas/v1/scan-request.schema.json",
    "result": "schemas/v2/scan-result.schema.json",
    "result_extension_analysis": "schemas/v2/extensions/analysis.schema.json",
    "result_extension_profiles": "schemas/v2/extensions/profiles.schema.json",
    "result_extension_artifacts": "schemas/v2/extensions/artifacts.schema.json",
    "result_extension_suppressions": "schemas/v2/extensions/suppressions.schema.json",
    "result_extension_runtime": "schemas/v2/extensions/runtime.schema.json",
    "facts": "schemas/facts/v1/facts.schema.json",
    "profile": "schemas/profiles/v1/profile.schema.json",
    "bitcode_artifact_set": "schemas/artifacts/v1/bitcode-artifact-set.schema.json",
    "llvm_facts": "schemas/ir-facts/v1/llvm-floating-point-facts.schema.json",
    "evidence": "schemas/evidence/v1/floating-point-evidence.schema.json",
    "binding_sidecar": "schemas/evidence/v1/binding-sidecar.schema.json",
    "build_context": "schemas/contexts/v1/context.schema.json",
    "cache_entry": "schemas/cache/v1/cache-entry.schema.json",
    "validation_corpus": "schemas/validation/v1/validation-corpus.schema.json",
    "validation_oracle": "schemas/validation/v1/validation-oracle.schema.json",
    "validation_result": "schemas/validation/v1/validation-result.schema.json",
}


@dataclass(frozen=True, slots=True)
class BitcodeArtifactSetRequest:
    artifact_root: Path
    manifest: str
    manifest_sha256: str
    required_profiles: tuple[str, ...]
    source_mapping: str


@dataclass(frozen=True, slots=True)
class ScanRequest:
    schema_version: str
    request_id: str
    project_root: Path
    source_profile: str
    target_profile: str
    input: Mapping[str, Any]
    rules_enabled: tuple[str, ...]
    rules_explicit: bool
    rule_versions: Mapping[str, str]
    budgets: Mapping[str, int | float]
    source_revision: str | None
    bitcode_artifact_set: BitcodeArtifactSetRequest | None
    source_build_context: Mapping[str, Any] | None
    target_build_context: Mapping[str, Any] | None
    suppressions: tuple[Suppression, ...]
    policy_as_of: str | None
    cache: CacheConfig


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}

    def schema(self, name: str) -> dict[str, Any]:
        if name not in SCHEMA_PATHS:
            raise KeyError(name)
        if name not in self._schemas:
            resource = files("floating_point_precision_scanner").joinpath(SCHEMA_PATHS[name])
            self._schemas[name] = json.loads(resource.read_text(encoding="utf-8"))
        return self._schemas[name]

    def validate(self, name: str, document: Mapping[str, Any]) -> list[Diagnostic]:
        if name == "result" and document.get("schemaVersion") != "2.0":
            return [
                diagnostic(
                    "unsupported-result-version",
                    "result_validation",
                    "扫描结果协议版本不受支持；只接受结果协议 2.0。",
                    "The scan result version is unsupported; only result schema 2.0 is accepted.",
                )
            ]
        validator = Draft202012Validator(self.schema(name), format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
        diagnostics = [
            diagnostic(
                "schema_validation_error",
                "request_validation" if name == "request" else f"{name}_validation",
                f"协议字段无效：{self._format_path(error.absolute_path)}。",
                f"Invalid protocol field: {self._format_path(error.absolute_path)}.",
                suggestion="请按对应 JSON Schema 修正该字段。",
                suggestion_en=f"Correct the field according to its JSON Schema: {error.message}",
            )
            for error in errors
        ]
        if name == "result" and not diagnostics:
            extension_schemas = {
                EXTENSION_ANALYSIS: "result_extension_analysis",
                EXTENSION_PROFILES: "result_extension_profiles",
                EXTENSION_ARTIFACTS: "result_extension_artifacts",
                EXTENSION_SUPPRESSIONS: "result_extension_suppressions",
                EXTENSION_RUNTIME: "result_extension_runtime",
            }
            extensions = cast(Mapping[str, Mapping[str, Any]], document["extensions"])
            for extension_name, schema_name in extension_schemas.items():
                diagnostics.extend(self.validate(schema_name, extensions[extension_name]))
            if not diagnostics:
                diagnostics.extend(self._result_invariants(document))
        return diagnostics

    @staticmethod
    def _result_invariants(document: Mapping[str, Any]) -> list[Diagnostic]:
        return [
            diagnostic(
                code,
                "result_validation",
                f"结果 v2 合同不变量不成立：{code}。",
                f"A result v2 contract invariant failed: {code}.",
            )
            for code in validate_result_invariants(document)
        ]

    @staticmethod
    def _format_path(parts: Any) -> str:
        rendered = ".".join(str(part) for part in parts)
        return rendered or "$"


def parse_request(
    document: Mapping[str, Any], registry: SchemaRegistry
) -> tuple[ScanRequest | None, list[Diagnostic]]:
    errors = registry.validate("request", document)
    if errors:
        return None, errors
    rules_document = document.get("rules")
    rules = rules_document if isinstance(rules_document, Mapping) else None
    schema_version = str(document["schema_version"])
    enabled, versions, rule_errors = normalize_rule_selection(rules, schema_version=schema_version)
    if rule_errors:
        return None, rule_errors
    build_contexts = document.get("build_contexts")
    source_build_context: Mapping[str, Any] | None = None
    target_build_context: Mapping[str, Any] | None = None
    if isinstance(build_contexts, Mapping):
        if schema_version not in {"1.3", "1.4"}:
            return None, [
                diagnostic(
                    "build_context_version_unsupported",
                    "request_validation",
                    "Build context 仅受 scan schema 1.3 及以上版本支持。",
                    "Build contexts are supported only by scan schema 1.3 and later.",
                )
            ]
        for side in ("source", "target"):
            value = build_contexts.get(side)
            if isinstance(value, Mapping):
                context_errors = registry.validate("build_context", value)
                if context_errors:
                    return None, context_errors
                if side == "source":
                    source_build_context = dict(value)
                else:
                    target_build_context = dict(value)
    suppression_values = document.get("suppressions", [])
    suppressions = parse_suppressions(
        [item for item in suppression_values if isinstance(item, Mapping)]
        if isinstance(suppression_values, list)
        else []
    )
    suppression_scopes: set[tuple[str, str, int | None, int | None]] = set()
    policy_as_of = str(document["policy_as_of"]) if document.get("policy_as_of") else None
    for item in suppressions:
        path = PurePosixPath(item.path.replace("\\", "/"))
        scope = (item.code, item.path, item.start_line, item.end_line)
        if (
            not item.reason.strip()
            or "\\" in item.path
            or path.is_absolute()
            or bool(re.match(r"^[A-Za-z]:", item.path))
            or ".." in path.parts
            or item.path in {"*", "**", "**/*"}
            or (item.start_line is None) != (item.end_line is None)
            or scope in suppression_scopes
            or (
                item.start_line is not None
                and item.end_line is not None
                and item.end_line < item.start_line
            )
            or (item.expires_on is not None and schema_version != "1.4")
            or (item.expires_on is not None and policy_as_of is None)
        ):
            return None, [
                diagnostic(
                    "invalid_suppression",
                    "request_validation",
                    "Suppression 路径或行范围无效。",
                    "The suppression path or line range is invalid.",
                )
            ]
        suppression_scopes.add(scope)
    cache_document = document.get("cache")
    cache = CacheConfig()
    if isinstance(cache_document, Mapping):
        if schema_version != "1.4":
            return None, [
                diagnostic(
                    "cache_version_unsupported",
                    "request_validation",
                    "分析缓存仅受 scan schema 1.4 支持。",
                    "Analysis caching is supported only by scan schema 1.4.",
                )
            ]
        mode = str(cache_document.get("mode", "off"))
        root_value = cache_document.get("root")
        root = Path(str(root_value)).resolve() if root_value else None
        project_root = Path(str(document["project_root"])).resolve()
        if mode not in CACHE_MODES or (mode != "off" and root is None):
            return None, [
                diagnostic(
                    "invalid_cache_configuration",
                    "request_validation",
                    "缓存模式或根目录无效。",
                    "The cache mode or root is invalid.",
                )
            ]
        if root is not None:
            try:
                root.relative_to(project_root)
            except ValueError:
                return None, [
                    diagnostic(
                        "cache_root_outside_project",
                        "request_validation",
                        "缓存根目录必须位于项目根目录内。",
                        "The cache root must be inside the project root.",
                    )
                ]
        cache = CacheConfig(
            mode,
            root,
            int(
                cache_document.get(
                    "max_entry_bytes",
                    document.get("budgets", {}).get("max_cache_entry_bytes", 67_108_864),
                )
            ),
        )
    bitcode_document = document.get("bitcode_artifact_set")
    bitcode_request = None
    if isinstance(bitcode_document, Mapping):
        bitcode_request = BitcodeArtifactSetRequest(
            artifact_root=Path(str(bitcode_document["artifact_root"])).resolve(),
            manifest=str(bitcode_document["manifest"]),
            manifest_sha256=str(bitcode_document["manifest_sha256"]),
            required_profiles=tuple(
                str(item)
                for item in bitcode_document.get("required_profiles", ["source-preserving"])
            ),
            source_mapping=str(bitcode_document.get("source_mapping", "best-effort")),
        )
    request = ScanRequest(
        schema_version=schema_version,
        request_id=str(document["request_id"]),
        project_root=Path(str(document["project_root"])).resolve(),
        source_profile=str(document["source_profile"]),
        target_profile=str(document["target_profile"]),
        input=dict(document["input"]),
        rules_enabled=enabled,
        rules_explicit=rules is not None,
        rule_versions=versions,
        budgets=dict(document.get("budgets", {})),
        source_revision=(
            str(document["source_revision"]) if document.get("source_revision") else None
        ),
        bitcode_artifact_set=bitcode_request,
        source_build_context=source_build_context,
        target_build_context=target_build_context,
        suppressions=suppressions,
        policy_as_of=policy_as_of,
        cache=cache,
    )
    return request, []
