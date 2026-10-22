from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable

from ..core import Diagnostic
from ..core.metadata import to_json_compatible


def aggregate_diagnostics(diagnostics: Iterable[Diagnostic]) -> list[str]:
    grouped: dict[tuple[str, str, str, str, str, str], list[Diagnostic]] = defaultdict(list)
    for item in diagnostics:
        reason = str(item.details.get("reason", ""))
        relation_kind = str(item.details.get("relationKind", ""))
        grouped[(item.code, item.stage, item.severity.value, reason, relation_kind, item.message)].append(item)
    output: list[str] = []
    for key in sorted(grouped):
        code, stage, severity, reason, relation_kind, message = key
        items = grouped[key]
        if len(items) == 1:
            output.append(message)
            continue
        locations = sorted(
            {
                f"{item.location.path}:{item.location.line}:{item.location.column or 0}"
                for item in items
                if item.location is not None
            }
        )
        references = sorted(
            {
                value
                for item in items
                for name, raw in item.details.items()
                if name.lower().endswith("id") or name.lower().endswith("ids")
                for value in _reference_values(raw)
            }
        )
        details = {
            "code": code,
            "stage": stage,
            "severity": severity,
            "reason": reason,
            "relationKind": relation_kind,
            "count": len(items),
            "locations": locations,
            "referenceIds": references,
        }
        output.append(f"{message} | aggregate={json.dumps(to_json_compatible(details), ensure_ascii=False, sort_keys=True, separators=(',', ':'))}")
    return output


def _reference_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)):
        return tuple(item for item in value if isinstance(item, str))
    return ()
