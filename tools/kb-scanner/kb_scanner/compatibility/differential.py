from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


ALLOWED_STATUSES = frozenset({"parity-required", "approved-correction", "deferred-blocking"})


def normalize_payload(value: Any, roots: Sequence[str] = ()) -> Any:
    if isinstance(value, Mapping):
        normalized = {str(key): normalize_payload(item, roots) for key, item in value.items()}
        if isinstance(normalized.get("findings"), list):
            normalized["findings"] = sorted(normalized["findings"], key=_finding_key)
        if isinstance(normalized.get("diagnostics"), list):
            normalized["diagnostics"] = sorted(normalized["diagnostics"], key=str)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_payload(item, roots) for item in value]
    if isinstance(value, str):
        result = value.replace("\\", "/")
        for root in sorted({item.replace("\\", "/").rstrip("/") for item in roots if item}, key=len, reverse=True):
            result = result.replace(root, "$ROOT")
        return result
    return value


def compare_payloads(expected: Any, actual: Any) -> tuple[str, ...]:
    differences: list[str] = []
    _compare(expected, actual, "$", differences)
    return tuple(differences)


def validate_ledger(payload: Any) -> tuple[str, ...]:
    failures: list[str] = []
    if not isinstance(payload, Mapping) or set(payload) != {"schemaVersion", "allowedStatuses", "decisions"}:
        return ("ledger root fields are invalid",)
    if payload["schemaVersion"] != "1.0" or set(payload["allowedStatuses"]) != ALLOWED_STATUSES:
        failures.append("ledger version or allowed statuses are invalid")
    decisions = payload["decisions"]
    if not isinstance(decisions, list):
        return (*failures, "ledger decisions must be an array")
    seen: set[str] = set()
    required = {"id", "status", "fixture", "field", "legacyValue", "newValue", "reason", "evidenceIds", "proofPathIds"}
    for index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping) or set(decision) != required:
            failures.append(f"decision[{index}] fields are invalid")
            continue
        identity = decision["id"]
        if not isinstance(identity, str) or not identity or identity in seen:
            failures.append(f"decision[{index}] identity is empty or duplicated")
        else:
            seen.add(identity)
        status = decision["status"]
        if status not in ALLOWED_STATUSES:
            failures.append(f"decision[{index}] status is invalid")
        if status == "approved-correction" and not (decision["evidenceIds"] or decision["proofPathIds"]):
            failures.append(f"decision[{index}] approved correction has no evidence or proof")
        if not all(isinstance(decision[name], str) and decision[name] for name in ("fixture", "field", "reason")):
            failures.append(f"decision[{index}] audit fields are incomplete")
    return tuple(failures)


def _finding_key(value: Any) -> tuple[object, ...]:
    if not isinstance(value, Mapping):
        return (str(value),)
    return (value.get("file", ""), value.get("line", 0), value.get("column") or 0, value.get("rule_id", ""), value.get("id", ""))


def _compare(expected: Any, actual: Any, path: str, output: list[str]) -> None:
    if type(expected) is not type(actual):
        output.append(f"{path}: type {type(expected).__name__} != {type(actual).__name__}")
        return
    if isinstance(expected, Mapping):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                output.append(f"{path}.{key}: unexpected")
            elif key not in actual:
                output.append(f"{path}.{key}: missing")
            else:
                _compare(expected[key], actual[key], f"{path}.{key}", output)
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            output.append(f"{path}: length {len(expected)} != {len(actual)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, f"{path}[{index}]", output)
    elif expected != actual:
        output.append(f"{path}: {expected!r} != {actual!r}")
