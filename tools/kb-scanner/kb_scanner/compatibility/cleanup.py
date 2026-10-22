from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any


ALLOWED_DISPOSITIONS = frozenset({"remove-after-golden", "removed", "retained-deferred"})


def validate_cleanup_inventory(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, Mapping) or set(payload) != {"schemaVersion", "entries"}:
        return ("cleanup inventory root fields are invalid",)
    failures: list[str] = []
    if payload["schemaVersion"] != "1.0":
        failures.append("cleanup inventory version is invalid")
    entries = payload["entries"]
    if not isinstance(entries, list):
        return (*failures, "cleanup entries must be an array")
    required = {"path", "replacement", "fixtures", "disposition", "exitCondition"}
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != required:
            failures.append(f"entry[{index}] fields are invalid")
            continue
        path = entry["path"]
        if not isinstance(path, str) or not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or path in seen:
            failures.append(f"entry[{index}] path is invalid or duplicated")
        else:
            seen.add(path)
        if entry["disposition"] not in ALLOWED_DISPOSITIONS:
            failures.append(f"entry[{index}] disposition is invalid")
        if not isinstance(entry["fixtures"], list) or not entry["fixtures"]:
            failures.append(f"entry[{index}] requires fixtures")
        if not isinstance(entry["replacement"], str) or not entry["replacement"] or not isinstance(entry["exitCondition"], str) or not entry["exitCondition"]:
            failures.append(f"entry[{index}] replacement or exit condition is missing")
    return tuple(failures)
