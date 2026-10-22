from __future__ import annotations

from collections import defaultdict

from ...core import Diagnostic
from .context import SourceContextProjector
from .models import TypedRef, V2Diagnostic, stable_view_id


class V2DiagnosticProjector:
    def __init__(self, source_context: SourceContextProjector) -> None:
        self._source_context = source_context

    def project(self, diagnostics: tuple[Diagnostic, ...]) -> tuple[V2Diagnostic, ...]:
        groups = defaultdict(list)
        for item in diagnostics:
            details = item.details or {}
            reason = _reason(details.get("reason") or details.get("reasonCode"))
            key = (item.code, item.stage, _severity(item.severity.value), reason, item.message, item.affects_exit_code)
            groups[key].append(item)
        result = []
        for (code, stage, severity, reason, message, affects), items in groups.items():
            refs = _refs(items)
            representative = next((item.location for item in items if item.location is not None), None)
            source = None
            if representative is not None:
                from ...core import SourceSpan
                source = self._source_context.project(SourceSpan(representative, representative))
            status = "unknown" if affects else "partial"
            result.append(V2Diagnostic(
                id=stable_view_id("diagnostic", code, stage, severity, reason, message), code=code,
                stage=stage, severity=severity, status=status, reasonCodes=(reason,), count=len(items),
                representativeLocation=source, findingIds=(), refs=refs,
            ))
        return tuple(sorted(result, key=lambda item: (item.severity, item.code, item.stage, item.id)))


def _severity(value: str) -> str:
    return {"warning": "medium", "error": "high", "fatal": "critical"}.get(value, "info")


def _reason(value: object) -> str:
    candidate = str(value or "missing_input").replace("-", "_")
    allowed = {"context_budget_exceeded", "context_unavailable", "cycle_detected", "dynamic_expression", "inactive_branch", "missing_input", "missing_reference", "multiple_candidates", "reference_budget_exceeded", "type_conflict", "configuration_conflict"}
    return candidate if candidate in allowed else "missing_input"


def _refs(items) -> tuple[TypedRef, ...]:
    values = {}
    for item in items:
        details = item.details or {}
        for key, kind in (("referenceId", "relation"), ("evidenceId", "evidence"), ("classificationId", "classification")):
            value = details.get(key)
            if isinstance(value, str):
                values[(kind, value)] = TypedRef(kind=kind, id=value, producer=item.producer or item.stage)
    return tuple(values[key] for key in sorted(values))
