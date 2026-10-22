from __future__ import annotations

from collections.abc import Mapping
from typing import Any


TOP_LEVEL_FIELDS = ("schemaVersion", "tool", "rulePack", "project", "summary", "findings", "diagnostics")
FINDING_FIELDS = (
    "id", "rule_id", "severity", "confidence", "title", "title_en", "file", "line", "column",
    "symbol", "reason", "reason_en", "suggestion", "suggestion_en", "snippet", "scan_mode",
    "finding_type", "source_kind", "is_actionable", "is_reference_source", "is_blocking",
    "arch_reachability", "branch_group_id", "branch_role", "compatible_sibling_branch",
    "compatible_branch_kind", "build_context", "alternative_impl", "condition_macros", "trace",
    "location", "context",
)
SUMMARY_FIELDS = (
    "files", "findings", "issues", "hints", "blocking", "portabilityGaps", "inactiveOrGuarded",
    "referenceSources", "references",
)


class ProjectionContractError(ValueError):
    pass


def validate_payload(payload: Mapping[str, Any]) -> None:
    if tuple(payload) != TOP_LEVEL_FIELDS or set(payload) != set(TOP_LEVEL_FIELDS):
        raise ProjectionContractError("schema 1.0 top-level fields or order changed")
    if payload["schemaVersion"] != "1.0":
        raise ProjectionContractError("schemaVersion must remain 1.0")
    for name in ("tool", "rulePack", "project", "summary"):
        if not isinstance(payload[name], Mapping):
            raise ProjectionContractError(f"{name} must be an object")
    if not isinstance(payload["findings"], list) or not isinstance(payload["diagnostics"], list):
        raise ProjectionContractError("findings and diagnostics must be arrays")
    summary = payload["summary"]
    for field in SUMMARY_FIELDS:
        if isinstance(summary.get(field), bool) or not isinstance(summary.get(field), int):
            raise ProjectionContractError(f"summary.{field} must be an integer")
    readiness = summary.get("readiness")
    if readiness is not None:
        _validate_readiness(readiness)
    for finding in payload["findings"]:
        if not isinstance(finding, Mapping) or set(finding) != set(FINDING_FIELDS):
            raise ProjectionContractError("finding fields changed")
        if not isinstance(finding["trace"], Mapping):
            raise ProjectionContractError("finding.trace must be an object")
        if finding["location"] != {"file": finding["file"], "line": finding["line"], "column": finding["column"]}:
            raise ProjectionContractError("finding.location must mirror compatibility position")
        if finding["context"] != {"snippet": finding["snippet"]}:
            raise ProjectionContractError("finding.context must mirror snippet")


def _validate_readiness(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ProjectionContractError("summary.readiness must be an object")
    required = {"state", "confidence", "dimensions", "blockingDimensions", "completeness", "staticScopeOnly", "compiled", "testsExecuted", "trace"}
    if set(value) != required:
        raise ProjectionContractError("summary.readiness fields changed")
    if value["staticScopeOnly"] is not True or value["compiled"] is not False or value["testsExecuted"] is not False:
        raise ProjectionContractError("readiness must remain explicitly static-only")
